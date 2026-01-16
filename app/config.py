from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
	port: int = 8080
	root_dirs: List[str] = ["C:\\", "D:\\"]
	auth_enabled: bool = False
	password_hash: str = ""  # bcrypt hash if enabled
	cors_allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"


settings = Settings()


