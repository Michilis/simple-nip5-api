from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.database import create_tables
from app.routes import public, admin, nostr_json
from app.services.scheduler import invoice_scheduler
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting NIP-05 API application...")
    
    # Create database tables
    create_tables()
    logger.info("Database tables created/verified")
    
    # Start invoice polling scheduler
    invoice_scheduler.start()
    logger.info("Invoice scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NIP-05 API application...")
    
    # Stop scheduler
    invoice_scheduler.stop()
    logger.info("Invoice scheduler stopped")

# Create FastAPI application
app = FastAPI(
    title="Simple NIP-05 API",
    description="A Lightning-powered NIP-05 identity service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(nostr_json.router)

# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Simple NIP-05 API",
        "status": "healthy",
        "version": "1.0.0",
        "domain": settings.DOMAIN
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "scheduler_running": invoice_scheduler.is_running,
        "domain": settings.DOMAIN,
        "endpoints": {
            "nostr_json": f"/.well-known/nostr.json",
            "create_invoice": "/api/public/invoice",
            "webhook": "/api/public/webhook/paid",
            "admin_add": "/api/whitelist/add",
            "admin_remove": "/api/whitelist/remove"
        }
    } 