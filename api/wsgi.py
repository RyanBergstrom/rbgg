"""
WSGI entry point for the rbgg API application.

Expose the FastAPI ``app`` instance so that any WSGI server can serve the API.
"""
from app import app


def application(environ, start_response):
    """Standard WSGI callable."""
    return app(environ, start_response)