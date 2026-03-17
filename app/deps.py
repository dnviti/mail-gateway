"""Shared FastAPI dependencies."""

import httpx
from fastapi import Request


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient stored in app state.

    The client is created during the application lifespan startup and
    closed on shutdown, ensuring proper connection-pool reuse across
    all outbound HTTP calls.
    """
    return request.app.state.httpx_client
