from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .routers import health, files
from .routers import admin as admin_router
from .auth import router as auth_router
from .middlewares import AuthMiddleware
from .db import init_db


def create_app() -> FastAPI:
	app = FastAPI(title="Remote File Explorer API", version="0.1.0")

	# CORS (adjust in .env if exposing publicly)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.cors_allow_origins,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	app.add_middleware(AuthMiddleware)

	app.include_router(health.router, prefix="/api")
	app.include_router(files.router, prefix="/api")
	app.include_router(auth_router, prefix="/api")
	app.include_router(admin_router.router, prefix="/api")

	# Initialize database
	init_db()

	# Serve CDN Vue frontend
	app.mount("/", StaticFiles(directory=str((__file__[:__file__.rfind("\\app\\")] + "\\frontend_cdn").replace("/","\\")), html=True), name="static")

	return app


app = create_app()


