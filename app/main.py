from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.database import build_engine, get_session
from app.models import AbuseReport, Base, ShortLink
from app.rate_limit import rate_limit
from app.schemas import (
    AbuseReportAdminView,
    AbuseReportCreate,
    AbuseReportCreated,
    AbuseReportResolve,
    AbuseReportResolved,
    HealthResponse,
    LinkCreate,
    LinkCreated,
    LinkDisabled,
    LinkStats,
)
from app.security import generate_code, token_hash, token_matches

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
logger = logging.getLogger("snaplink")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = build_engine(settings)
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    app.state.redis = None

    if settings.redis_url:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True,
                                socket_connect_timeout=3, socket_timeout=3,
                                health_check_interval=30)
        try:
            await client.ping()
            app.state.redis = client
        except Exception as exc:
            await client.aclose()
            logger.error("Redis startup check failed: %s", type(exc).__name__)
            if settings.environment == "production":
                await engine.dispose()
                raise RuntimeError("Redis is required in production")
            logger.warning("Continuing without Redis; development rate limits are process-local")

    if settings.auto_create_tables and settings.environment != "production":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        if app.state.redis is not None:
            await app.state.redis.aclose()
        await engine.dispose()


def link_status(link: ShortLink, now: datetime | None = None) -> Literal["active", "expired", "disabled"]:
    """Return the effective status, including time-based expiration."""
    if not link.is_active:
        return "disabled"

    current = now or datetime.now(timezone.utc)
    expiration = link.expires_at
    if expiration is not None:
        # SQLite test databases may return naive datetimes even when the model
        # uses timezone=True. Interpret those values as UTC for consistency.
        if expiration.tzinfo is None or expiration.utcoffset() is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        else:
            expiration = expiration.astimezone(timezone.utc)
        if expiration <= current:
            return "expired"

    return "active"


def unavailable_link_page(kind: Literal["expired", "disabled", "not_found"]) -> HTMLResponse:
    """A visitor-friendly page shown instead of a raw JSON 404 for dead links."""
    content = {
        "expired": (
            "This short link has expired",
            "ohhhhh NAAAUUURRRRR the link is goneeeeeee 😢",
            "But don't worry, you can create a new short link for the same destination.",
            "⌛",
        ),
        "disabled": (
            "This short link is no longer active",
            "ohhhhh NAAAUUURRRRR the link is goneeeeeee 😢",
            "But don't worry, you can create a new short link for the same destination.",
            "⏸",
        ),
        "not_found": (
            "We couldn't find this link",
            "ohhhhh NAAAUUURRRRR the link is goneeeeeee 😢",
            "But don't worry, you can create a new short link for the same destination.",
            "🔎",
        ),
    }[kind]
    title, description, code_label, icon = content
    status_code = 404 if kind == "not_found" else 410
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#5b4bdb">
  <title>{title} · SnapLink</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #201d35; background: #f8f8fc; }}
    * {{ box-sizing: border-box; }}
    body {{ min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 24px; background: radial-gradient(ellipse at 15% 5%, #eeeaff 0, transparent 38%), radial-gradient(ellipse at 95% 80%, #eafaf5 0, transparent 32%), #f8f8fc; }}
    main {{ width: min(100%, 560px); padding: clamp(28px, 6vw, 48px); text-align: center; border: 1px solid #efedf7; background: white; border-radius: 24px; box-shadow: 0 24px 70px rgba(42,34,93,.09); }}
    .brand {{ display: inline-flex; align-items: center; gap: 9px; margin-bottom: 34px; font-weight: 800; font-size: 19px; }}
    .mark {{ display: grid; place-items: center; width: 34px; height: 34px; border-radius: 11px; background: #5b4bdb; color: white; font-size: 21px; }}
    .icon {{ display: grid; place-items: center; width: 68px; height: 68px; margin: 0 auto 20px; border-radius: 22px; background: #f0edff; font-size: 31px; }}
    .code {{ color: #706b86; font-size: 10px; font-weight: 800; letter-spacing: 1.7px; text-transform: uppercase; }}
    h1 {{ margin: 11px 0 12px; font-size: clamp(26px, 5vw, 36px); letter-spacing: -1.2px; line-height: 1.15; }}
    p {{ margin: 0 auto; max-width: 400px; color: #77758b; font-size: 14px; line-height: 1.75; }}
    a {{ display: inline-flex; margin-top: 27px; padding: 13px 18px; border-radius: 11px; background: #5b4bdb; color: white; font-size: 13px; font-weight: 750; text-decoration: none; }}
    a:hover {{ background: #4939c7; }}
    .http-code {{ margin-top: 23px; color: #aaa7b9; font-size: 10px; }}
  </style>
</head>
<body>
  <main>
    <div class="brand"><span class="mark">↗</span><span>SnapLink</span></div>
    <div class="icon" aria-hidden="true">{icon}</div>
    <div class="code">The link isn't available</div>
    <h1>{title}</h1>
    <p>{description}</p>
    <a href="/">Go to SnapLink</a>
    <div class="http-code">{code_label}</div>
  </main>
</body>
</html>'''
    return HTMLResponse(
        content=html,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not logging.getLogger().handlers:
        logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "A production-oriented URL shortener with persistent links, custom aliases, "
            "expiration, click statistics, link management tokens, and rate limiting."
        ),
        lifespan=lifespan,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )
    application.state.settings = settings
    application.state.local_rate_limits = {}
    application.state.local_rate_limits_lock = asyncio.Lock()
    application.state.redis = None

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-Management-Token"],
            allow_credentials=False,
        )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Request-ID"] = secrets.token_hex(16)
        if request.app.state.settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.url.path == "/" or request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @application.get("/", include_in_schema=False)
    async def homepage() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @application.get("/static/{asset_name}", include_in_schema=False)
    async def static_asset(asset_name: str) -> FileResponse:
        # Only known static assets are served; user input is never used as a filesystem path.
        assets = {
            "app.js": (STATIC_DIR / "app.js", "text/javascript"),
            "styles.css": (STATIC_DIR / "styles.css", "text/css"),
            "favicon.svg": (STATIC_DIR / "favicon.svg", "image/svg+xml"),
        }
        asset = assets.get(asset_name)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        return FileResponse(asset[0], media_type=asset[1])

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    @application.get("/healthz", response_model=HealthResponse, tags=["operations"])
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get("/readyz", response_model=HealthResponse, tags=["operations"])
    async def readiness(request: Request) -> HealthResponse:
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
            client = request.app.state.redis
            if client is not None:
                await client.ping()
            elif request.app.state.settings.environment == "production":
                raise RuntimeError("Redis is not configured")
        except Exception as exc:
            logger.warning("Readiness check failed: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Service is not ready") from exc
        return HealthResponse(status="ready")

    @application.post(
        "/api/v1/links",
        response_model=LinkCreated,
        status_code=201,
        tags=["links"],
        dependencies=[Depends(rate_limit("create", fail_closed=True))],
    )
    async def create_link(
        payload: LinkCreate,
        request: Request,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> LinkCreated:
        settings = request.app.state.settings
        if len(payload.url) > settings.max_url_length:
            raise HTTPException(status_code=422, detail=f"URL must be at most {settings.max_url_length} characters")
        management_token = secrets.token_urlsafe(32)
        attempts = 1 if payload.custom_alias else 5

        for _ in range(attempts):
            code = payload.custom_alias or generate_code(settings.short_code_length)
            link = ShortLink(
                code=code,
                original_url=payload.url,
                management_token_hash=token_hash(management_token),
                expires_at=payload.expires_at,
                click_count=0,
                is_active=True,
            )
            session.add(link)
            try:
                await session.commit()
                base_url = settings.public_base_url or str(request.base_url).rstrip("/")
                return LinkCreated(
                    code=link.code,
                    short_url=f"{base_url}/{link.code}",
                    original_url=link.original_url,
                    created_at=link.created_at,
                    expires_at=link.expires_at,
                    management_token=management_token,
                )
            except IntegrityError as exc:
                await session.rollback()
                if payload.custom_alias:
                    raise HTTPException(status_code=409, detail="That custom alias is already in use") from exc
                logger.warning("Generated code collision; retrying")
            except SQLAlchemyError as exc:
                await session.rollback()
                logger.error("Database operation failed while creating a short link: %s", type(exc).__name__)
                raise HTTPException(status_code=503, detail="Link creation is temporarily unavailable") from exc

        raise HTTPException(status_code=503, detail="Could not generate a unique short link; retry")

    async def authorized_link(
        code: str,
        management_token: str | None,
        session: AsyncSession,
    ) -> ShortLink:
        try:
            result = await session.execute(select(ShortLink).where(ShortLink.code == code))
            link = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error("Database operation failed while checking link authorization: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Link management is temporarily unavailable") from exc
        if link is None or not management_token or not token_matches(management_token, link.management_token_hash):
            # A uniform 404 makes it harder to enumerate links or test token validity.
            raise HTTPException(status_code=404, detail="Link or management token not found")
        return link

    @application.get(
        "/api/v1/links/{code}/stats",
        response_model=LinkStats,
        tags=["links"],
        dependencies=[Depends(rate_limit("stats", fail_closed=True))],
    )
    async def link_stats(
        code: str,
        session: Annotated[AsyncSession, Depends(get_session)],
        management_token: Annotated[str | None, Header(alias="X-Management-Token")] = None,
    ) -> LinkStats:
        link = await authorized_link(code, management_token, session)
        effective_status = link_status(link)
        return LinkStats(
            code=link.code,
            original_url=link.original_url,
            click_count=link.click_count,
            created_at=link.created_at,
            expires_at=link.expires_at,
            last_clicked_at=link.last_clicked_at,
            is_active=effective_status == "active",
            status=effective_status,
        )

    @application.delete(
        "/api/v1/links/{code}",
        response_model=LinkDisabled,
        tags=["links"],
        dependencies=[Depends(rate_limit("stats", fail_closed=True))],
    )
    async def disable_link(
        code: str,
        session: Annotated[AsyncSession, Depends(get_session)],
        management_token: Annotated[str | None, Header(alias="X-Management-Token")] = None,
    ) -> LinkDisabled:
        link = await authorized_link(code, management_token, session)
        link.is_active = False
        try:
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Database operation failed while disabling link: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Link management is temporarily unavailable") from exc
        return LinkDisabled(code=code, is_active=False, message="Link disabled")

    @application.post(
        "/api/v1/reports",
        response_model=AbuseReportCreated,
        status_code=201,
        tags=["abuse reports"],
        dependencies=[Depends(rate_limit("report", fail_closed=True))],
    )
    async def create_abuse_report(
        payload: AbuseReportCreate,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> AbuseReportCreated:
        try:
            existing_link = await session.scalar(
                select(ShortLink.id).where(ShortLink.code == payload.code)
            )
            if existing_link is None:
                raise HTTPException(status_code=404, detail="Short link not found")
            report = AbuseReport(
                code=payload.code,
                category=payload.category,
                details=payload.details,
                status="open",
            )
            session.add(report)
            await session.commit()
            return AbuseReportCreated(
                id=report.id,
                code=report.code,
                status=report.status,
                created_at=report.created_at,
            )
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Database operation failed while recording an abuse report: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Reporting is temporarily unavailable") from exc

    def require_admin(candidate: str | None, request: Request) -> None:
        expected = request.app.state.settings.admin_api_key
        if not expected or not candidate or not secrets.compare_digest(candidate, expected):
            # Do not reveal whether the administrative API is enabled or the key is close.
            raise HTTPException(status_code=404, detail="Not found")

    @application.get(
        "/api/v1/admin/reports",
        response_model=list[AbuseReportAdminView],
        tags=["administration"],
        dependencies=[Depends(rate_limit("stats", fail_closed=True))],
    )
    async def list_abuse_reports(
        request: Request,
        session: Annotated[AsyncSession, Depends(get_session)],
        status: Literal["open", "resolved"] = Query(default="open"),
        limit: int = Query(default=50, ge=1, le=100),
        admin_api_key: Annotated[str | None, Header(alias="X-Admin-API-Key")] = None,
    ) -> list[AbuseReportAdminView]:
        require_admin(admin_api_key, request)
        try:
            result = await session.execute(
                select(AbuseReport)
                .where(AbuseReport.status == status)
                .order_by(AbuseReport.created_at.desc())
                .limit(limit)
            )
            reports = result.scalars().all()
            return [
                AbuseReportAdminView(
                    id=report.id,
                    code=report.code,
                    category=report.category,
                    details=report.details,
                    status=report.status,
                    created_at=report.created_at,
                    resolved_at=report.resolved_at,
                )
                for report in reports
            ]
        except SQLAlchemyError as exc:
            logger.error("Database operation failed while listing abuse reports: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Administration is temporarily unavailable") from exc

    @application.post(
        "/api/v1/admin/reports/{report_id}/resolve",
        response_model=AbuseReportResolved,
        tags=["administration"],
        dependencies=[Depends(rate_limit("stats", fail_closed=True))],
    )
    async def resolve_abuse_report(
        report_id: int,
        payload: AbuseReportResolve,
        request: Request,
        session: Annotated[AsyncSession, Depends(get_session)],
        admin_api_key: Annotated[str | None, Header(alias="X-Admin-API-Key")] = None,
    ) -> AbuseReportResolved:
        require_admin(admin_api_key, request)
        try:
            result = await session.execute(
                select(AbuseReport).where(AbuseReport.id == report_id)
            )
            report = result.scalar_one_or_none()
            if report is None:
                raise HTTPException(status_code=404, detail="Report not found")

            link_disabled = False
            if payload.disable_link:
                link_result = await session.execute(
                    select(ShortLink).where(ShortLink.code == report.code)
                )
                link = link_result.scalar_one_or_none()
                if link is not None and link.is_active:
                    link.is_active = False
                    link_disabled = True

            if report.status != "resolved":
                report.status = "resolved"
                report.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            return AbuseReportResolved(
                id=report.id,
                status=report.status,
                link_disabled=link_disabled,
                resolved_at=report.resolved_at or datetime.now(timezone.utc),
            )
        except HTTPException:
            await session.rollback()
            raise
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Database operation failed while resolving an abuse report: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Administration is temporarily unavailable") from exc

    @application.get(
        "/{code}",
        include_in_schema=False,
        dependencies=[Depends(rate_limit("redirect", fail_closed=False))],
    )
    async def redirect_short_link(
        code: str,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> RedirectResponse:
        now = datetime.now(timezone.utc)
        statement = (
            update(ShortLink)
            .where(
                ShortLink.code == code,
                ShortLink.is_active.is_(True),
                or_(ShortLink.expires_at.is_(None), ShortLink.expires_at > now),
            )
            .values(click_count=ShortLink.click_count + 1, last_clicked_at=now)
            .returning(ShortLink.original_url)
        )
        try:
            result = await session.execute(statement)
            destination = result.scalar_one_or_none()
            await session.commit()
            if destination is not None:
                return RedirectResponse(
                    url=destination,
                    status_code=302,
                    headers={"Cache-Control": "no-store"},
                )

            # Explain why the short link did not redirect instead of returning
            # an unhelpful JSON error to a visitor who clicked an old link.
            lookup = await session.execute(select(ShortLink).where(ShortLink.code == code))
            link = lookup.scalar_one_or_none()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Database operation failed while resolving a short link: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Redirect service is temporarily unavailable") from exc

        if link is None:
            return unavailable_link_page("not_found")
        status = link_status(link, now)
        if status == "expired":
            return unavailable_link_page("expired")
        if status == "disabled":
            return unavailable_link_page("disabled")
        # A rare concurrent update can cause the atomic redirect to miss. Do
        # not redirect unless the update actually incremented the click count.
        return unavailable_link_page("not_found")

    return application


app = create_app()
