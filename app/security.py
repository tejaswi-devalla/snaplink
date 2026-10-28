from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
from urllib.parse import urlsplit

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")
RESERVED_CODES = {
    "api", "docs", "redoc", "openapi", "openapi.json", "healthz", "readyz",
    "favicon.ico", "robots.txt", "static", "terms", "privacy", "report",
}


def generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def validate_destination(url: str, max_length: int = 4096) -> str:
    """Validate a redirect destination without making a network request to it."""
    value = url.strip()
    if not value or len(value) > max_length:
        raise ValueError(f"URL must contain 1–{max_length} characters")
    if CONTROL_OR_SPACE.search(value):
        raise ValueError("URL must not contain whitespace or control characters")

    try:
        parsed = urlsplit(value)
        # Accessing .port forces urllib to validate malformed port values.
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("URL is malformed") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are permitted")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing embedded credentials are not permitted")

    host = parsed.hostname.rstrip(".").lower()
    if not host:
        raise ValueError("URL must include a valid hostname")
    if host == "localhost" or host.endswith((
        ".localhost", ".local", ".internal", ".test", ".invalid", ".example", ".home.arpa"
    )):
        raise ValueError("Local or reserved hostnames are not permitted")

    # Accept public IP literals, but reject private/reserved ones. Also reject
    # ambiguous numeric host forms such as 127.1 that browsers may treat as IPs.
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            raise ValueError("Private, loopback, and reserved IP destinations are not permitted")
    else:
        if re.fullmatch(r"[0-9.]+", host):
            raise ValueError("Malformed numeric hostname")
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("URL hostname is invalid") from exc
        if len(ascii_host) > 253 or "." not in ascii_host:
            raise ValueError("URL must use a public fully qualified hostname")
        labels = ascii_host.split(".")
        label_pattern = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
        if any(not label_pattern.fullmatch(label) for label in labels):
            raise ValueError("URL hostname is invalid")

    return value


def validate_alias(alias: str | None) -> str | None:
    if alias is None:
        return None
    alias = alias.strip()
    if not ALIAS_PATTERN.fullmatch(alias):
        raise ValueError("Custom alias must be 4–32 characters: letters, numbers, '_' or '-'")
    if alias.lower() in RESERVED_CODES or alias.lower().endswith(".json"):
        raise ValueError("That custom alias is reserved")
    return alias


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(candidate: str, stored_hash: str) -> bool:
    import hmac

    return hmac.compare_digest(token_hash(candidate), stored_hash)
