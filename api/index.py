"""
Vercel serverless entry point.

Vercel imports this file and calls the `app` ASGI object for every request.
All routing is handled by FastAPI — this file just wires it up.

Vercel requirement: the ASGI app must be named `app` or exported from here.
"""
import sys
import os

# Ensure the api/ directory is on the Python path so `from app.xxx` works
sys.path.insert(0, os.path.dirname(__file__))

from app.main import app  # noqa: F401  — Vercel picks this up automatically
