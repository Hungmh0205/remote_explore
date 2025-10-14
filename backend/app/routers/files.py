import os
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..path_utils import resolve_path


router = APIRouter()


class Entry(BaseModel):
	name: str
	path: str
	is_dir: bool
	size: int
	modified: float  # epoch seconds


@router.get("/list", response_model=List[Entry])
def list_dir(path: str = Query("")):
	allowed, abs_dir = resolve_path(path or ".")
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isdir(abs_dir):
		raise HTTPException(status_code=404, detail="Directory not found")
	entries: List[Entry] = []
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
	return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


@router.get("/file")
def get_file(path: str):
	allowed, abs_file = resolve_path(path)
	if not allowed:
		raise HTTPException(status_code=403, detail="Path not allowed")
	if not os.path.isfile(abs_file):
		raise HTTPException(status_code=404, detail="File not found")
	filename = os.path.basename(abs_file)
	return FileResponse(abs_file, filename=filename)


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
	# If destination is an existing dir, move inside keeping name
	if os.path.isdir(abs_dst):
		target = os.path.join(abs_dst, os.path.basename(abs_src))
	else:
		target = abs_dst
	shutil.move(abs_src, target)
	return {"ok": True, "path": target}


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


