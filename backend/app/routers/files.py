import os
import shutil
import tempfile
import zipfile
import secrets
from typing import Dict
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from ..path_utils import resolve_path
from ..db import query_all, execute, query_one
import hashlib
from ..config import settings
import stat as _stat


def _detect_windows_drives() -> List[str]:
	try:
		import string
		drives = []
		for letter in string.ascii_uppercase:
			path = f"{letter}:\\"
			if os.path.exists(path):
				drives.append(path)
		return drives
	except Exception:
		return []


router = APIRouter()
# (Search endpoint removed as per user request)

# ---------------- Pins Endpoints ----------------

@router.get("/pins")
def list_pins() -> List[str]:
	rows = query_all("SELECT path FROM pins ORDER BY id DESC")
	return [r["path"] for r in rows]


class PinBody(BaseModel):
	path: str


@router.post("/pins")
def add_pin(body: PinBody):
	# store if not exists
	try:
		execute("INSERT OR IGNORE INTO pins(path, created_at) VALUES(?, strftime('%s','now'))", (body.path,))
	except Exception:
		pass
	return {"ok": True}


@router.delete("/pins")
def remove_pin(path: str):
	execute("DELETE FROM pins WHERE path = ?", (path,))
	return {"ok": True}



class Entry(BaseModel):
	name: str
	path: str
	is_dir: bool
	size: int
	modified: float  # epoch seconds
# In-memory undo store: token -> inverse operation data
_UNDO_STORE: Dict[str, dict] = {}
# Shares will be persisted in SQLite; keep a tiny read-through cache if needed (not required now)



@router.get("/list", response_model=List[Entry])
def list_dir(path: str = Query("")):
	allowed, abs_dir = resolve_path(path or ".")
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isdir(abs_dir):
		raise HTTPException(status_code=404, detail="Directory not found")
	entries: List[Entry] = []
	try:
		with os.scandir(abs_dir) as it:
			for entry in it:
				try:
					stat = entry.stat(follow_symlinks=False)
				except Exception:
					continue
				entries.append(
					Entry(
						name=entry.name,
						path=os.path.join(abs_dir, entry.name),
						is_dir=entry.is_dir(follow_symlinks=False),
						size=0 if entry.is_dir(follow_symlinks=False) else int(stat.st_size),
						modified=float(stat.st_mtime),
					)
				)
	except PermissionError:
		raise HTTPException(status_code=403, detail="Access denied: insufficient permissions to read this directory")
	return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


@router.get("/roots", response_model=List[str])
def get_roots():
	# Prefer dynamic Windows drive detection; fallback to configured roots
	drives = _detect_windows_drives()
	if drives:
		return drives
	return settings.root_dirs


@router.get("/file")
def get_file(path: str):
	allowed, abs_file = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isfile(abs_file):
		raise HTTPException(status_code=404, detail="File not found")
	filename = os.path.basename(abs_file)
	return FileResponse(abs_file, filename=filename)


@router.get("/open")
def open_inline(path: str):
	"""Open file inline in browser (no attachment filename header)."""
	allowed, abs_file = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isfile(abs_file):
		raise HTTPException(status_code=404, detail="File not found")
	return FileResponse(abs_file)


@router.get("/zip")
def download_zip(path: str):
	"""Zip a folder (or single file) and stream as ZIP download."""
	allowed, abs_path = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	basename = os.path.basename(abs_path.rstrip("/\\")) or "archive"
	# create temp zip
	tmp_dir = tempfile.mkdtemp(prefix="rfe_")
	zip_path = os.path.join(tmp_dir, f"{basename}.zip")
	with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
		if os.path.isdir(abs_path):
			for root, dirs, files in os.walk(abs_path):
				for fname in files:
					full = os.path.join(root, fname)
					rel = os.path.relpath(full, start=os.path.dirname(abs_path))
					zf.write(full, arcname=rel)
		else:
			zf.write(abs_path, arcname=basename)
	# return file and schedule cleanup by OS (temp dir)
	return FileResponse(zip_path, filename=f"{basename}.zip")


class MultipleZipBody(BaseModel):
	paths: List[str]


@router.post("/zip/multiple")
def download_multiple_zip(body: MultipleZipBody):
	"""Zip multiple files/folders and stream as ZIP download."""
	if not body.paths:
		raise HTTPException(status_code=400, detail="No paths provided")
	
	# Validate all paths
	valid_paths = []
	for path in body.paths:
		allowed, abs_path = resolve_path(path)
		if not allowed:
			raise HTTPException(status_code=403, detail=f"Path not allowed: {path}")
		if not os.path.exists(abs_path):
			raise HTTPException(status_code=404, detail=f"Path not found: {path}")
		valid_paths.append(abs_path)
	
	# Create temp zip
	tmp_dir = tempfile.mkdtemp(prefix="rfe_")
	zip_path = os.path.join(tmp_dir, "selected_files.zip")
	
	with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
		for abs_path in valid_paths:
			basename = os.path.basename(abs_path.rstrip("/\\"))
			if os.path.isdir(abs_path):
				# Add folder contents
				for root, dirs, files in os.walk(abs_path):
					for fname in files:
						full = os.path.join(root, fname)
						rel = os.path.relpath(full, start=abs_path)
						arcname = f"{basename}/{rel}"
						zf.write(full, arcname=arcname)
			else:
				# Add single file
				zf.write(abs_path, arcname=basename)
	
	return FileResponse(zip_path, filename="selected_files.zip")


@router.post("/upload")
async def upload_file(dest: str, file: UploadFile = File(...)):
	allowed, abs_dest = resolve_path(dest)
	if not allowed:
		raise HTTPException(status_code=403, detail="Destination not allowed")
	if not os.path.isdir(abs_dest):
		raise HTTPException(status_code=404, detail="Destination directory not found")
	target_path = os.path.join(abs_dest, file.filename)
	try:
		with open(target_path, "wb") as f:
			while True:
				chunk = await file.read(1024 * 1024)
				if not chunk:
					break
				f.write(chunk)
	finally:
		await file.close()
	return {"ok": True, "path": target_path}


class MkdirBody(BaseModel):
	path: str


@router.post("/mkdir")
def make_dir(body: MkdirBody):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	os.makedirs(abs_path, exist_ok=True)
	return {"ok": True}


class DeleteBody(BaseModel):
	path: str


@router.post("/delete")
def delete_path(body: DeleteBody):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	if os.path.isdir(abs_path):
		shutil.rmtree(abs_path)
	else:
		os.remove(abs_path)
	return {"ok": True}


class RenameBody(BaseModel):
	path: str
	new_name: str


@router.post("/rename")
def rename_path(body: RenameBody):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	parent = os.path.dirname(abs_path)
	new_path = os.path.join(parent, body.new_name)
	if os.path.exists(new_path):
		raise HTTPException(status_code=409, detail="Target exists")
	os.replace(abs_path, new_path)
	return {"ok": True, "path": new_path}


class MoveBody(BaseModel):
	source: str
	destination: str  # file path (new name) or directory path


@router.post("/move")
def move_path(body: MoveBody):
	allowed_src, abs_src = resolve_path(body.source)
	allowed_dst, abs_dst = resolve_path(body.destination)
	if not (allowed_src and allowed_dst):
		raise HTTPException(status_code=403, detail="Path not allowed")
	# Prevent moving a directory into itself or its subdirectory
	abs_src_norm = os.path.normcase(os.path.normpath(abs_src))
	abs_dst_norm = os.path.normcase(os.path.normpath(abs_dst))
	if os.path.isdir(abs_src):
		if abs_dst_norm == abs_src_norm or abs_dst_norm.startswith(abs_src_norm + os.sep):
			raise HTTPException(status_code=400, detail="Cannot move a directory into itself")
	# If destination is an existing dir, move inside keeping name
	if os.path.isdir(abs_dst):
		target = os.path.join(abs_dst, os.path.basename(abs_src))
	else:
		target = abs_dst
	# No-op if target equals source
	target_norm = os.path.normcase(os.path.normpath(target))
	if target_norm == abs_src_norm:
		return {"ok": True, "path": target, "skipped": True}
	shutil.move(abs_src, target)
	# Register undo token to move back
	token = secrets.token_urlsafe(16)
	_UNDO_STORE[token] = {"type": "move", "src": target, "dst": abs_src}
	return {"ok": True, "path": target, "undo_token": token}


class UndoBody(BaseModel):
	token: str
class ShareCreateBody(BaseModel):
    path: str
    readonly: bool = True
    allow_download: bool = True
    allow_edit: bool = False
    expires_hours: Optional[float] = None  # None => no expiry


@router.post("/share/create")
def create_share_link(body: ShareCreateBody, request: Request):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	token = secrets.token_urlsafe(16)
	expires_at = None
	if body.expires_hours is not None and body.expires_hours > 0:
		expires_at = (datetime.utcnow().timestamp() + float(body.expires_hours) * 3600.0)
	# persist share
	execute(
		"INSERT INTO shares(token, root, readonly, allow_download, allow_edit, expires_at) VALUES(?,?,?,?,?,?)",
		(
			token,
			abs_path,
			1 if bool(body.readonly) else 0,
			1 if bool(body.allow_download) else 0,
			1 if bool(body.allow_edit) else 0,
			expires_at,
		),
	)
	base = str(request.base_url).rstrip("/")
	share_url = f"{base}/shared.html?token={token}"
	return {"ok": True, "token": token, "url": share_url, "expires_at": expires_at}


def _get_share_or_410(token: str) -> dict:
	share = query_one("SELECT * FROM shares WHERE token = ?", (token,))
	if not share:
		raise HTTPException(status_code=404, detail="Share not found")
	expires_at = share.get("expires_at")
	if expires_at is not None and datetime.utcnow().timestamp() > float(expires_at):
		execute("DELETE FROM shares WHERE token = ?", (token,))
		raise HTTPException(status_code=410, detail="Share expired")
	return share


def _verify_password_or_401(share: dict, supplied_password):
	return None


def _touch_access(token: str) -> None:
	return None


def _resolve_share_path(token: str, rel_path: str, password: Optional[str] = None) -> str:
    share = _get_share_or_410(token)
    _verify_password_or_401(share, password)
    base = share["root"]
    # Reject absolute rel paths to avoid base being ignored by join
    if rel_path and os.path.isabs(rel_path):
        raise HTTPException(status_code=403, detail="Absolute paths are not allowed in share")
    # Use realpath to resolve symlinks where supported
    target = os.path.realpath(os.path.join(base, rel_path or "."))
    # Normalize for comparison: path, case (Windows), and ensure separator boundary
    base_norm = os.path.normcase(os.path.normpath(os.path.realpath(base)))
    target_norm = os.path.normcase(os.path.normpath(target))
    if not (target_norm == base_norm or target_norm.startswith(base_norm + os.sep)):
        raise HTTPException(status_code=403, detail="Path outside share")
    _touch_access(token)
    return target


@router.get("/share/list", response_model=List[Entry])
def share_list(token: str, path: str = ""):
	abs_target = _resolve_share_path(token, path)
	if not os.path.isdir(abs_target):
		raise HTTPException(status_code=404, detail="Directory not found")
	entries: List[Entry] = []
	with os.scandir(abs_target) as it:
		for entry in it:
			try:
				stat = entry.stat(follow_symlinks=False)
			except Exception:
				continue
			entries.append(
				Entry(
					name=entry.name,
					path=os.path.join(abs_target, entry.name),
					is_dir=entry.is_dir(follow_symlinks=False),
					size=0 if entry.is_dir(follow_symlinks=False) else int(stat.st_size),
					modified=float(stat.st_mtime),
				)
			)
	return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


@router.get("/share/file")
def share_file(token: str, path: str, download: bool = False):
	share = _get_share_or_410(token)
	abs_file = _resolve_share_path(token, path)
	if not os.path.isfile(abs_file):
		raise HTTPException(status_code=404, detail="File not found")
	if download and not bool(share.get("allow_download")):
		raise HTTPException(status_code=403, detail="Download not allowed")
	filename = os.path.basename(abs_file)
	return FileResponse(abs_file, filename=filename if download else None)


@router.get("/share/read", response_class=PlainTextResponse)
def share_read(token: str, path: str):
	abs_target = _resolve_share_path(token, path)
	if not os.path.isfile(abs_target):
		raise HTTPException(status_code=404, detail="File not found")
	with open(abs_target, "r", encoding="utf-8", errors="replace") as f:
		return f.read()


class ShareSaveBody(BaseModel):
	token: str
	path: str
	content: str


@router.post("/share/save")
def share_save(body: ShareSaveBody):
	share = query_one("SELECT * FROM shares WHERE token = ?", (body.token,))
	if not share:
		raise HTTPException(status_code=404, detail="Share not found")
	if not bool(share.get("allow_edit")):
		raise HTTPException(status_code=403, detail="Edit not allowed")
	abs_target = _resolve_share_path(body.token, body.path)
	parent = os.path.dirname(abs_target)
	os.makedirs(parent, exist_ok=True)
	with open(abs_target, "w", encoding="utf-8", newline="") as f:
		f.write(body.content)
	return {"ok": True}


@router.get("/share/info")
def share_info(token: str):
	share = query_one("SELECT * FROM shares WHERE token = ?", (token,))
	if not share:
		raise HTTPException(status_code=404, detail="Share not found")
	return {
        "allow_edit": bool(share.get("allow_edit", 0)),
        "allow_download": bool(share.get("allow_download", 0)),
        "readonly": bool(share.get("readonly", 1))
	}


class ShareMultipleZipBody(BaseModel):
	token: str
	paths: List[str]


@router.post("/share/zip/multiple")
def share_download_multiple_zip(body: ShareMultipleZipBody):
	"""Zip multiple files/folders from a share and stream as ZIP download."""
	share = query_one("SELECT * FROM shares WHERE token = ?", (body.token,))
	if not share:
		raise HTTPException(status_code=404, detail="Share not found")
	
	if not body.paths:
		raise HTTPException(status_code=400, detail="No paths provided")
	
	# Validate all paths within share scope
	valid_paths = []
	for rel_path in body.paths:
		abs_path = _resolve_share_path(body.token, rel_path)
		if not abs_path or not os.path.exists(abs_path):
			raise HTTPException(status_code=404, detail=f"Path not found: {rel_path}")
		valid_paths.append(abs_path)
	
	# Create temp zip
	tmp_dir = tempfile.mkdtemp(prefix="rfe_share_")
	zip_path = os.path.join(tmp_dir, "selected_files.zip")
	
	with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
		for abs_path in valid_paths:
			basename = os.path.basename(abs_path.rstrip("/\\"))
			if os.path.isdir(abs_path):
				# Add folder contents
				for root, dirs, files in os.walk(abs_path):
					for fname in files:
						full = os.path.join(root, fname)
						rel = os.path.relpath(full, start=abs_path)
						arcname = f"{basename}/{rel}"
						zf.write(full, arcname=arcname)
			else:
				# Add single file
				zf.write(abs_path, arcname=basename)
	
	return FileResponse(zip_path, filename="selected_files.zip")


@router.post("/undo")
def undo_action(body: UndoBody):
	data = _UNDO_STORE.pop(body.token, None)
	if not data:
		raise HTTPException(status_code=404, detail="Undo token not found")
	if data.get("type") == "move":
		src = data.get("src")  # current location
		dst = data.get("dst")  # original location
		if not (src and dst):
			raise HTTPException(status_code=400, detail="Invalid undo data")
		# Validate paths are still allowed
		ok_src, abs_src = resolve_path(src)
		ok_dst, abs_dst = resolve_path(dst)
		if not (ok_src and ok_dst):
			raise HTTPException(status_code=403, detail="Path not allowed")
		# If destination exists, refuse to overwrite
		if os.path.exists(abs_dst):
			raise HTTPException(status_code=409, detail="Destination exists; cannot undo")
		# Ensure parent exists
		os.makedirs(os.path.dirname(abs_dst), exist_ok=True)
		shutil.move(abs_src, abs_dst)
		return {"ok": True, "path": abs_dst}
	raise HTTPException(status_code=400, detail="Unsupported undo type")


class SaveBody(BaseModel):
	path: str
	content: str


@router.post("/save")
def save_text_file(body: SaveBody):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	parent = os.path.dirname(abs_path)
	os.makedirs(parent, exist_ok=True)
	with open(abs_path, "w", encoding="utf-8", newline="") as f:
		f.write(body.content)
	return {"ok": True}


@router.get("/read", response_class=PlainTextResponse)
def read_text_file(path: str):
	allowed, abs_path = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isfile(abs_path):
		raise HTTPException(status_code=404, detail="File not found")
	try:
		with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
			return f.read()
	except UnicodeDecodeError:
		raise HTTPException(status_code=415, detail="Not a text file")


# ---------------- Metadata (Normal & Share) ----------------

def _build_metadata(abs_path: str) -> dict:
	s = os.stat(abs_path)
	is_dir = os.path.isdir(abs_path)
	# Writable for current user/process
	writable = bool(s.st_mode & _stat.S_IWRITE) if os.name == 'nt' else os.access(abs_path, os.W_OK)
	return {
		"name": os.path.basename(abs_path.rstrip("/\\")) or abs_path,
		"path": abs_path,
		"is_dir": is_dir,
		"size": 0 if is_dir else int(s.st_size),
		"modified": float(s.st_mtime),
		"created": float(getattr(s, 'st_ctime', s.st_mtime)),
		"mode": int(s.st_mode),
		"readonly": not writable,
	}


def _update_meta_abs(abs_path: str, modified: Optional[float], readonly: Optional[bool]) -> dict:
	# Update modified time
	if modified is not None:
		try:
			atime = os.stat(abs_path).st_atime
			os.utime(abs_path, (float(atime), float(modified)))
		except Exception:
			raise HTTPException(status_code=400, detail="Failed to update modified time")
	# Update readonly flag (best-effort)
	if readonly is not None:
		try:
			mode = os.stat(abs_path).st_mode
			if readonly:
				# Remove write bit(s)
				if os.name == 'nt':
					os.chmod(abs_path, mode & ~_stat.S_IWRITE)
				else:
					os.chmod(abs_path, mode & ~(_stat.S_IWUSR | _stat.S_IWGRP | _stat.S_IWOTH))
			else:
				# Add owner write bit
				os.chmod(abs_path, mode | _stat.S_IWUSR)
		except Exception:
			raise HTTPException(status_code=400, detail="Failed to update readonly flag")
	return {"ok": True, "meta": _build_metadata(abs_path)}


@router.get("/stat")
def stat_path(path: str):
	allowed, abs_path = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	return _build_metadata(abs_path)


class UpdateMetaBody(BaseModel):
	path: str
	modified: Optional[float] = None
	readonly: Optional[bool] = None


@router.post("/update_meta")
def update_meta(body: UpdateMetaBody):
	allowed, abs_path = resolve_path(body.path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	return _update_meta_abs(abs_path, body.modified, body.readonly)


@router.get("/share/stat")
def share_stat(token: str, path: str):
	abs_path = _resolve_share_path(token, path)
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	return _build_metadata(abs_path)


class ShareUpdateMetaBody(BaseModel):
	token: str
	path: str
	modified: Optional[float] = None
	readonly: Optional[bool] = None


@router.post("/share/update_meta")
def share_update_meta(body: ShareUpdateMetaBody):
	share = query_one("SELECT * FROM shares WHERE token = ?", (body.token,))
	if not share:
		raise HTTPException(status_code=404, detail="Share not found")
	if not bool(share.get("allow_edit")):
		raise HTTPException(status_code=403, detail="Edit not allowed")
	abs_path = _resolve_share_path(body.token, body.path)
	if not os.path.exists(abs_path):
		raise HTTPException(status_code=404, detail="Path not found")
	return _update_meta_abs(abs_path, body.modified, body.readonly)

class CopyBody(BaseModel):
	source: str
	destination: str  # file path (new name) or directory path


@router.post("/copy")
def copy_path(body: CopyBody):
	allowed_src, abs_src = resolve_path(body.source)
	allowed_dst, abs_dst = resolve_path(body.destination)
	if not (allowed_src and allowed_dst):
		raise HTTPException(status_code=403, detail="Path not allowed")
	if os.path.isdir(abs_dst):
		target = os.path.join(abs_dst, os.path.basename(abs_src))
	else:
		target = abs_dst
	if os.path.isdir(abs_src):
		if os.path.exists(target):
			raise HTTPException(status_code=409, detail="Target exists")
		shutil.copytree(abs_src, target)
	else:
		# ensure parent exists
		os.makedirs(os.path.dirname(target), exist_ok=True)
		shutil.copy2(abs_src, target)
	return {"ok": True, "path": target}


