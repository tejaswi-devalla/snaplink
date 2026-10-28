from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time


def create_link(client, **payload):
    base = {"url": "https://example.com/products?id=42"}
    base.update(payload)
    return client.post("/api/v1/links", json=base)


def test_homepage_and_health(client):
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "SnapLink" in homepage.text
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_create_redirect_and_click_analytics(client):
    created = create_link(client, custom_alias="demo-link")
    assert created.status_code == 201
    data = created.json()
    assert data["code"] == "demo-link"
    assert data["short_url"] == "https://snap.test/demo-link"
    assert data["management_token"]

    redirected = client.get("/demo-link", follow_redirects=False)
    assert redirected.status_code == 302
    assert redirected.headers["location"] == "https://example.com/products?id=42"
    assert redirected.headers["referrer-policy"] == "no-referrer"

    stats = client.get(
        "/api/v1/links/demo-link/stats",
        headers={"X-Management-Token": data["management_token"]},
    )
    assert stats.status_code == 200
    assert stats.json()["click_count"] == 1
    assert stats.json()["original_url"] == "https://example.com/products?id=42"


def test_stats_require_management_token(client):
    data = create_link(client, custom_alias="private-link").json()
    assert client.get("/api/v1/links/private-link/stats").status_code == 404
    assert client.get(
        "/api/v1/links/private-link/stats",
        headers={"X-Management-Token": "not-the-token"},
    ).status_code == 404
    assert data["management_token"]


def test_duplicate_custom_alias_returns_conflict(client):
    assert create_link(client, custom_alias="same-alias").status_code == 201
    duplicate = create_link(client, custom_alias="same-alias")
    assert duplicate.status_code == 409


def test_invalid_schemes_and_private_hosts_are_rejected(client):
    assert client.post("/api/v1/links", json={"url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/api/v1/links", json={"url": "file:///etc/passwd"}).status_code == 422
    assert client.post("/api/v1/links", json={"url": "http://127.0.0.1/admin"}).status_code == 422
    assert client.post("/api/v1/links", json={"url": "http://localhost/"}).status_code == 422


def test_expiration_requires_future_timezone_aware_datetime(client):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert create_link(client, expires_at=past).status_code == 422
    naive = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
    assert create_link(client, expires_at=naive).status_code == 422



def test_expired_link_shows_visitor_page_and_expired_analytics_status(client):
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    data = create_link(client, custom_alias="expires-soon", expires_at=expiry).json()
    time.sleep(1.2)

    response = client.get("/expires-soon", follow_redirects=False)
    assert response.status_code == 410
    assert "This short link has expired" in response.text
    assert "Go to SnapLink" in response.text

    stats = client.get(
        "/api/v1/links/expires-soon/stats",
        headers={"X-Management-Token": data["management_token"]},
    )
    assert stats.status_code == 200
    assert stats.json()["status"] == "expired"
    assert stats.json()["is_active"] is False

def test_disable_link_prevents_future_redirects(client):
    data = create_link(client, custom_alias="disable-me").json()
    response = client.delete(
        "/api/v1/links/disable-me",
        headers={"X-Management-Token": data["management_token"]},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    disabled_page = client.get("/disable-me", follow_redirects=False)
    assert disabled_page.status_code == 410
    assert "This short link is no longer active" in disabled_page.text


def test_custom_alias_validation_and_reserved_words(client):
    assert create_link(client, custom_alias="bad alias").status_code == 422
    assert create_link(client, custom_alias="docs").status_code == 422


def test_rate_limit_is_enforced(client):
    # The fixture's limit is 25; hit that many times then check the next request.
    for _ in range(25):
        assert client.post("/api/v1/links", json={"url": "https://example.com"}).status_code == 201
    limited = client.post("/api/v1/links", json={"url": "https://example.com"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_abuse_report_admin_review_and_link_disable(client):
    data = create_link(client, custom_alias="report-target").json()
    report = client.post(
        "/api/v1/reports",
        json={"code": "report-target", "category": "phishing", "details": "Fake login page"},
    )
    assert report.status_code == 201
    report_data = report.json()
    assert report_data["status"] == "open"

    assert client.get("/api/v1/admin/reports").status_code == 404
    headers = {"X-Admin-API-Key": "test-admin-secret-key-with-at-least-32-chars"}
    queue = client.get("/api/v1/admin/reports", headers=headers)
    assert queue.status_code == 200
    assert any(item["id"] == report_data["id"] for item in queue.json())

    resolved = client.post(
        f"/api/v1/admin/reports/{report_data['id']}/resolve",
        headers=headers,
        json={"disable_link": True},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["link_disabled"] is True
    assert client.get("/report-target", follow_redirects=False).status_code == 410


def test_abuse_report_rejects_unknown_code_and_bad_category(client):
    missing = client.post(
        "/api/v1/reports",
        json={"code": "unknown-code", "category": "spam"},
    )
    assert missing.status_code == 404
    data = create_link(client, custom_alias="report-target").json()
    invalid = client.post(
        "/api/v1/reports",
        json={"code": data["code"], "category": "made-up-category"},
    )
    assert invalid.status_code == 422
