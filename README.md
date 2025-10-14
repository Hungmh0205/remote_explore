Remote File Explorer (FastAPI + Vue)

Quick start
- Backend: FastAPI (Python 3.10+)
- Frontend: Vue 3 + Vite

Setup
- Backend
  - cd backend
  - python -m venv .venv && .\.venv\Scripts\activate
  - pip install -r requirements.txt
  - powershell .\run.ps1
- Frontend
  - cd frontend
  - npm i
  - npm run dev

Access
- Vue CDN (no build): http://localhost:8080
- Vite dev (optional): http://localhost:5173

Config
- Edit `backend/app/config.py` or set env via `.env` (PORT, ROOT_DIRS, AUTH_ENABLED, PASSWORD_HASH)

Tunnel (optional)
- ngrok http 8080  (or 5173 for Vite dev)


