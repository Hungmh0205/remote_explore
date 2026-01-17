from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
	port: int = 8080
	root_dirs: List[str] = ["C:\\", "D:\\"]
	auth_enabled: bool = True
	password_hash: str = "$2b$12$BF.eoNGvGNVBReBIexf9DOjciaXk91DKflqBmTefVEUTLur17zmuq"  # bcrypt hash for 'admintest'
	cors_allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
	log_file: str = "remote_explorer.log"

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"


settings = Settings()


