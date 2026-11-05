@echo off
REM Start the FastAPI backend server on port 8000
set PYTHONPATH=d:\College\RenewOps
d:\College\RenewOps\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

