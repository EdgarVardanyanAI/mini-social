from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_prometheus import PrometheusMiddleware, metrics

from app.core.router import router
from app.core.settings import settings
from app.core.startups import initialize_project

app = FastAPI(
    debug=settings.DEBUG,
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_PATH}/openapi.json",
    docs_url=f"{settings.API_PATH}/docs",
)

app.include_router(router, prefix=settings.API_PATH)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.add_event_handler("startup", initialize_project)
