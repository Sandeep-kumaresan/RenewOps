@echo off
REM Start the MCP server on port 8001
set PYTHONPATH=d:\College\RenewOps
d:\College\RenewOps\venv\Scripts\uvicorn app.mcp.run:app --host 0.0.0.0 --port 8001 --reload

