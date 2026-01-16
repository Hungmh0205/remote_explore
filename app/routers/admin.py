from typing import List, Dict
from fastapi import APIRouter, HTTPException

from ..db import query_all, execute


router = APIRouter()


@router.get("/admin/summary")
def admin_summary() -> Dict[str, int]:
	shares = query_all("SELECT COUNT(1) as c FROM shares")
	pins = query_all("SELECT COUNT(1) as c FROM pins")
	return {"shares": int(shares[0]["c"]) if shares else 0, "pins": int(pins[0]["c"]) if pins else 0}


@router.get("/admin/shares")
def admin_list_shares() -> List[dict]:
	rows = query_all("SELECT token, root, readonly, allow_download, allow_edit, expires_at FROM shares ORDER BY rowid DESC")
	# normalize booleans
	for r in rows:
		r["readonly"] = bool(r.get("readonly", 0))
		r["allow_download"] = bool(r.get("allow_download", 0))
		r["allow_edit"] = bool(r.get("allow_edit", 0))
	return rows


@router.delete("/admin/shares")
def admin_delete_share(token: str):
	execute("DELETE FROM shares WHERE token = ?", (token,))
	return {"ok": True}


@router.get("/admin/pins")
def admin_list_pins() -> List[dict]:
	rows = query_all("SELECT id, path, created_at FROM pins ORDER BY id DESC")
	return rows


@router.delete("/admin/pins")
def admin_delete_pin(id: int):
	execute("DELETE FROM pins WHERE id = ?", (id,))
	return {"ok": True}


@router.post("/admin/shares/cleanup")
def admin_cleanup_shares() -> Dict[str, int]:
    # Remove expired shares only
    expired = query_all("SELECT token FROM shares WHERE expires_at IS NOT NULL AND expires_at < strftime('%s','now')")
    count_expired = len(expired)
    for r in expired:
        execute("DELETE FROM shares WHERE token = ?", (r["token"],))
    return {"expired": count_expired}



