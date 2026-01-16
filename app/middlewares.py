from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .auth import is_authenticated


class AuthMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next):
		if request.url.path.startswith("/api") and not request.url.path.endswith("/login"):
			if settings.auth_enabled and not is_authenticated(request):
				from starlette.responses import JSONResponse
				return JSONResponse({"detail": "Unauthorized"}, status_code=401)
		return await call_next(request)


