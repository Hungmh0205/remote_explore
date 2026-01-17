from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .routers import health, files
from .routers import admin as admin_router
from .routers import console as console_router
from .routers import monitoring as monitoring_router
from .routers import watcher as watcher_router
from .auth import router as auth_router
from .routers import services, processes, automation
from .middlewares import AuthMiddleware
from .db import init_db
from . import image_utils


@asynccontextmanager
async def lifespan(app: FastAPI):
	# Startup
	image_utils.init_pool()
	init_db()
	yield
	# Shutdown
	image_utils.shutdown_pool()


def create_app() -> FastAPI:
	app = FastAPI(title="Remote File Explorer API", version="0.1.0", lifespan=lifespan)

	# CORS (adjust in .env if exposing publicly)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.cors_allow_origins,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	app.add_middleware(AuthMiddleware)
	app.add_middleware(GZipMiddleware, minimum_size=1000)

	app.include_router(health.router, prefix="/api")
	app.include_router(files.router, prefix="/api")
	app.include_router(auth_router, prefix="/api")
	app.include_router(admin_router.router, prefix="/api")
	app.include_router(console_router.router, prefix="/api")
	app.include_router(monitoring_router.router, prefix="/api")
	app.include_router(watcher_router.router, prefix="/api")
	app.include_router(services.router, prefix="/api")
	app.include_router(processes.router, prefix="/api")
	app.include_router(automation.router, prefix="/api")

	# Serve CDN Vue frontend
	app.mount("/", StaticFiles(directory=str((__file__[:__file__.rfind("\\app\\")] + "\\frontend_cdn").replace("/","\\")), html=True), name="static")

	return app


app = create_app()


