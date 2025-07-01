from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from datetime import datetime
import logging

from app.routes import public, admin, nostr_json
from app.services.scheduler import invoice_scheduler
from app.services.startup import startup_manager
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    
    # Startup
    logger.info("Starting NIP-05 API application...")
    
    # Run comprehensive startup checks
    startup_status = await startup_manager.run_startup_checks()
    
    # Check if startup was successful
    if startup_status["status"] == "degraded":
        # Log critical errors but continue running (some issues may be non-critical)
        logger.warning("Application started with some issues - check logs above")
    
    # Start invoice polling scheduler
    invoice_scheduler.start()
    
    # Log LNbits status
    if settings.LNBITS_ENABLED:
        logger.info("LNbits integration enabled - Lightning payments available")
    else:
        logger.info("LNbits integration disabled - Admin-only registration mode")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NIP-05 API application...")
    
    # Stop scheduler
    invoice_scheduler.stop()
    logger.info("Application shutdown complete")

def custom_openapi():
    """Generate custom OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Simple NIP-05 API",
        version="1.0.0",
        description="""
## Lightning-Powered NIP-05 Identity Service

A comprehensive NIP-05 identity service that supports both Lightning payments and admin-only registration modes.

### Features
- 🚀 **Lightning Payments**: Integrated with LNbits for instant Bitcoin payments
- 🆔 **NIP-05 Identity**: Full NIP-05 identity verification support  
- 🔗 **Nostr Sync**: Automatic username sync from Nostr profiles
- 🛡️ **Admin Controls**: Secure API for user management
- ⚙️ **Flexible Modes**: Lightning mode or admin-only mode

### Operating Modes

#### ⚡ Lightning Mode (`LNBITS_ENABLED=true`)
- Public registration via Lightning payments
- Automatic payment processing
- Background invoice monitoring

#### 👨‍💼 Admin-Only Mode (`LNBITS_ENABLED=false`)  
- Manual registration only
- No payment processing
- Pure NIP-05 identity service

### Authentication
Admin endpoints require the `X-API-Key` header with your admin API key.

### Response Formats
All endpoints return JSON responses with consistent error handling.
        """,
        routes=app.routes,
        tags=[
            {
                "name": "public",
                "description": "Public endpoints for Lightning payment registration and user information"
            },
            {
                "name": "admin", 
                "description": "Admin endpoints for user management (requires API key)"
            },
            {
                "name": "nostr",
                "description": "NIP-05 identity resolution endpoint"
            },
            {
                "name": "health",
                "description": "Health check and status endpoints"
            }
        ]
    )
    
    # Add custom info
    openapi_schema["info"]["contact"] = {
        "name": "NIP-05 API Support",
        "url": "https://github.com/your-repo",
        "email": "support@yourdomain.com"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Let Swagger UI automatically use the current URL
    # When no servers are specified, Swagger UI uses the current request URL
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Create FastAPI application
app = FastAPI(
    title="Simple NIP-05 API",
    description="A Lightning-powered NIP-05 identity service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable ReDoc
    openapi_url="/openapi.json"
)

# Set custom OpenAPI
app.openapi = custom_openapi

# Add CORS middleware conditionally
if settings.CORS_ENABLED:
    logger.info(f"CORS enabled with origins: {settings.CORS_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.cors_methods_list,
        allow_headers=settings.cors_headers_list,
    )
else:
    logger.info("CORS disabled - assuming handled by nginx/webserver")

# Include routers
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(nostr_json.router)

# Custom Swagger UI endpoint
@app.get("/api-docs", include_in_schema=False)
async def api_documentation():
    """Serve Swagger UI documentation"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="NIP-05 API Documentation",
        swagger_favicon_url="https://nostr.build/i/nostr.png",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "operationsSorter": "method",
            "filter": True,
            "tryItOutEnabled": True
        }
    )

# Health check endpoint
@app.get("/", tags=["health"], summary="Basic health check", include_in_schema=False)
async def root():
    """
    Basic health check endpoint
    
    Returns basic service information and status.
    """
    from app.services.whitelist import whitelist_service
    
    return {
        "service": "Simple NIP-05 API",
        "status": "healthy",
        "version": "1.0.0",
        "domain": settings.DOMAIN,
        "lnbits_enabled": settings.LNBITS_ENABLED,
        "username_sync_enabled": settings.USERNAME_SYNC_ENABLED,
        "cors_enabled": settings.CORS_ENABLED,
        "nostr_dm_enabled": settings.NOSTR_DM_ENABLED,
        "whitelist_status": whitelist_service.get_whitelist_status(),
        "documentation": "/api-docs"
    }

@app.get("/health", tags=["health"], summary="Detailed health check")
async def health_check():
    """
    Detailed health check endpoint
    
    Returns comprehensive system status including:
    - Service health status
    - Server uptime
    - Enabled features  
    - Startup checks status
    - Database information
    """
    from app.services.whitelist import whitelist_service
    
    # Get startup status
    startup_status = startup_manager.get_startup_status()
    
    # Calculate uptime
    uptime_seconds = int(startup_status["uptime_seconds"])
    uptime_formatted = "Unknown"
    
    if uptime_seconds > 0:
        # Format uptime as human-readable string
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        if days > 0:
            uptime_formatted = f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            uptime_formatted = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            uptime_formatted = f"{minutes}m {seconds}s"
        else:
            uptime_formatted = f"{seconds}s"
    
    return {
        "status": startup_status["status"],
        "uptime_seconds": uptime_seconds,
        "uptime": uptime_formatted,
        "startup_checks": {
            "passed": startup_status["checks_passed"],
            "total": startup_status["total_checks"],
            "details": startup_status["checks"],
            "errors": startup_status["errors"]
        },
        "scheduler_running": invoice_scheduler.is_running,
        "domain": settings.DOMAIN,
        "features": {
            "lnbits_enabled": settings.LNBITS_ENABLED,
            "username_sync_enabled": settings.USERNAME_SYNC_ENABLED,
            "admin_only_mode": not settings.LNBITS_ENABLED,
            "cors_enabled": settings.CORS_ENABLED,
            "nostr_dm_enabled": settings.NOSTR_DM_ENABLED
        },
        "whitelist_status": whitelist_service.get_whitelist_status(),
        "database": startup_manager.get_database_info(),
        "documentation": "/api-docs"
    } 