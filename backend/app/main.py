import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.routers import auth, users, sei_config, sei_process, artifacts, documents, audit

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Silence noisy third-party loggers even in DEBUG mode
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("multipart").setLevel(logging.WARNING)
logging.getLogger("passlib").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  DEBUG              : %s", settings.DEBUG)
    logger.info("  ENVIRONMENT        : %s", settings.ENVIRONMENT)
    logger.info("  SEI WRITE OPS      : %s", settings.SEI_ENABLE_WRITE_OPERATIONS)
    logger.info("  RATE LIMIT/min     : %s", settings.RATE_LIMIT_PER_MINUTE)
    logger.info("  UPLOAD DIR         : %s", settings.UPLOAD_DIR)
    logger.info("=" * 60)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — allow configured origins + Chrome/Edge extension origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.perf_counter()
    # Log incoming request
    client = request.client.host if request.client else "unknown"
    logger.info(
        "→ %s %s  [client=%s]",
        request.method, request.url.path, client,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error(
            "✗ %s %s  %.0fms  EXCEPTION: %s",
            request.method, request.url.path, elapsed, exc,
        )
        raise
    elapsed = (time.perf_counter() - start) * 1000
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    symbol = "✓" if response.status_code < 400 else "✗"
    logger.log(
        level,
        "%s %s %s  %.0fms  [%s]",
        symbol, request.method, request.url.path, elapsed, response.status_code,
    )
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    )
    # Remove server fingerprinting
    try:
        del response.headers["server"]
    except KeyError:
        pass
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"] if loc != "body"),
            "message": error["msg"],
        })
    logger.warning(
        "422 Validation error on %s %s: %s",
        request.method, request.url.path, errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(
        "500 Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno do servidor. Tente novamente mais tarde."},
    )


# Routers
PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(sei_config.router, prefix=PREFIX)
app.include_router(sei_process.router, prefix=PREFIX)
app.include_router(artifacts.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(audit.router, prefix=PREFIX)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
