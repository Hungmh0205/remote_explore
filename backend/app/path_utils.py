import os
from typing import Tuple

from .config import settings


def normalize_path(input_path: str) -> str:
	"""Normalize Windows/Unix-like input to an absolute Windows path."""
	if not input_path:
		return ""
	# Replace forward slashes with backslashes for Windows
	win_path = input_path.replace("/", "\\")
	# Expand drive-only cases like "C:" to "C:\\"
	if len(win_path) == 2 and win_path[1] == ":":
		win_path = win_path + "\\"
	# If path is relative, keep as-is; operations will join with allowed roots as needed
	return os.path.normpath(win_path)


def is_within_allowed_roots(abs_path: str) -> bool:
	"""Check if absolute path is within any allowed root (drive or configured directory)."""
	try:
		abs_path = os.path.abspath(abs_path)
	except Exception:
		return False
	for root in settings.root_dirs:
		root_norm = os.path.normpath(root)
		# If root is a drive like C:\, allow any path starting with that drive
		try:
			common = os.path.commonpath([abs_path, root_norm])
		except Exception:
			continue
		if common == os.path.normpath(root_norm):
			return True
	return False


def resolve_path(request_path: str) -> Tuple[bool, str]:
	"""Resolve a request path to an absolute path and confirm it is allowed.

	Returns (allowed, absolute_path).
	"""
	if not request_path:
		return False, ""
	normalized = normalize_path(request_path)
	# If already absolute like C:\foo, use it; else try to join with first root
	if os.path.isabs(normalized):
		abs_target = os.path.abspath(normalized)
	else:
		# Default to first configured root when relative
		base = settings.root_dirs[0] if settings.root_dirs else os.getcwd()
		abs_target = os.path.abspath(os.path.join(base, normalized))
	allowed = is_within_allowed_roots(abs_target)
	return allowed, abs_target


