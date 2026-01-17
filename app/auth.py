from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
import bcrypt

from .config import settings


SESSION_COOKIE = "rfe_session_v2"


class LoginBody(BaseModel):
	password: str


router = APIRouter()


def is_authenticated(request: Request) -> bool:
	if not settings.auth_enabled:
		return True
	return request.cookies.get(SESSION_COOKIE) == "1"


def require_auth(request: Request):
	if not is_authenticated(request):
		raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/login")
def login(body: LoginBody, response: Response):
	if not settings.auth_enabled:
		# if auth disabled, always succeed
		response.set_cookie(SESSION_COOKIE, "1", httponly=True, samesite="lax")
		return {"ok": True, "disabled": True}
	if not settings.password_hash:
		raise HTTPException(status_code=500, detail="Password hash not configured")
	try:
		ok = bcrypt.checkpw(body.password.encode("utf-8"), settings.password_hash.encode("utf-8"))
	except Exception:
		raise HTTPException(status_code=500, detail="Auth error")
	if not ok:
		raise HTTPException(status_code=401, detail="Invalid credentials")
	response.set_cookie(SESSION_COOKIE, "1", httponly=True, samesite="lax")
	return {"ok": True}


@router.post("/logout")
def logout(response: Response):
	response.delete_cookie(SESSION_COOKIE)
	return {"ok": True}


