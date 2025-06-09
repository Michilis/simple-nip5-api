#!/usr/bin/env python3
"""
Simple NIP-05 API - Entry Point

This script starts the FastAPI application using uvicorn.
"""

import uvicorn
from config import settings

if __name__ == "__main__":
    # Run the FastAPI application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    ) 