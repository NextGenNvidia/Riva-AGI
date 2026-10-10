"""CORS Middleware configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Backend.config import config


def setup_cors(app: FastAPI) -> None:
    """Configures CORS to permit requests from configured origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
