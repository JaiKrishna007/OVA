from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import AppException, app_exception_handler, generic_exception_handler, generate_request_id
from app.routers.auth import router as auth_router
from app.routers.audit import router as audit_router
from app.routers.patients import router as patients_router
from app.routers.followups import router as followups_router
from app.routers.records import router as records_router
from app.routers.summaries import router as summaries_router
from app.routers.eval import router as eval_router
from app.routers.import_transfer import router as import_router
from app.routers.claims import router as claims_router
from app.routers.conflicts import router as conflicts_router
from app.routers.gaps import router as gaps_router
from app.routers.hospital_admin import router as hospital_admin_router
from app.routers.transfers import router as transfers_router
from app.routers.consents import router as consents_router



class SecurityAndRequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="OVA — Fertility Treatment & Follow-Up Assistant",
        description="Doctor-facing fertility assistant API (Kernel Prime'26, SW-01)",
        version="0.1.0",
    )

    # Security & Request Tracking Middleware
    app.add_middleware(SecurityAndRequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app|.*\.onrender\.com)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Routers mounted under /api/v1 and root for maximum client compatibility
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(patients_router, prefix="/api/v1")
    app.include_router(followups_router, prefix="/api/v1")
    app.include_router(records_router, prefix="/api/v1")
    app.include_router(summaries_router, prefix="/api/v1")
    app.include_router(eval_router, prefix="/api/v1")
    app.include_router(import_router, prefix="/api/v1")
    app.include_router(claims_router, prefix="/api/v1")
    app.include_router(conflicts_router, prefix="/api/v1")
    app.include_router(gaps_router, prefix="/api/v1")
    app.include_router(hospital_admin_router, prefix="/api/v1")
    app.include_router(transfers_router, prefix="/api/v1")
    app.include_router(consents_router, prefix="/api/v1")

    # Direct mount as well
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(patients_router)
    app.include_router(followups_router)
    app.include_router(records_router)
    app.include_router(summaries_router)
    app.include_router(eval_router)
    app.include_router(import_router)
    app.include_router(claims_router)
    app.include_router(conflicts_router)
    app.include_router(gaps_router)
    app.include_router(hospital_admin_router)
    app.include_router(transfers_router)
    app.include_router(consents_router)


    @app.get("/health", tags=["system"])
    @app.get("/api/v1/health", tags=["system"])
    async def health_check():
        from app.core.config import settings
        return {"status": "ok", "llm_provider": settings.LLM_PROVIDER}

    return app


app = create_app()
