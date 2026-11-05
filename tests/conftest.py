"""
Pytest configuration - sets up isolated test environment before any module loads.
"""

import os

# Set DATABASE_URL to SQLite before any app module imports settings
os.environ["DATABASE_URL"] = "sqlite:///./test_renewops.db"
os.environ["MCP_API_KEY"] = ""
os.environ["ADMIN_API_KEY"] = ""

