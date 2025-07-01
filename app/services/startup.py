import logging
import os
from datetime import datetime
from typing import Dict, Any

from app.database import create_tables, verify_database_schema, get_table_columns, table_exists, engine
from app.services.whitelist import whitelist_service
from config import settings

logger = logging.getLogger(__name__)

class StartupManager:
    """Manages application startup tasks and health checks"""
    
    def __init__(self):
        self.startup_time = None
        self.startup_checks = {
            "database": False,
            "schema": False,
            "whitelist": False,
            "config": False
        }
        self.startup_errors = []
        
    async def run_startup_checks(self) -> Dict[str, Any]:
        """Run all startup checks and return status"""
        self.startup_time = datetime.utcnow()
        logger.info("=== NIP-05 API Startup Checks ===")
        
        # Check 1: Database Creation and Migration
        try:
            logger.info("1. Checking database...")
            create_tables()
            self.startup_checks["database"] = True
            logger.info("✓ Database initialized successfully")
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.startup_errors.append(error_msg)
        
        # Check 2: Schema Verification
        try:
            logger.info("2. Verifying database schema...")
            if verify_database_schema():
                self.startup_checks["schema"] = True
                logger.info("✓ Database schema verified successfully")
            else:
                raise Exception("Schema verification failed")
        except Exception as e:
            error_msg = f"Database schema verification failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.startup_errors.append(error_msg)
        
        # Check 3: Configuration Validation
        try:
            logger.info("3. Validating configuration...")
            self._validate_configuration()
            self.startup_checks["config"] = True
            logger.info("✓ Configuration validated successfully")
        except Exception as e:
            error_msg = f"Configuration validation failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.startup_errors.append(error_msg)
        
        # Check 4: Whitelist Synchronization
        try:
            logger.info("4. Synchronizing whitelist...")
            whitelist_stats = whitelist_service.sync_whitelist_to_database()
            if any(whitelist_stats.values()):
                logger.info(f"✓ Whitelist sync: {whitelist_stats['added']} added, {whitelist_stats['updated']} updated, {whitelist_stats['deactivated']} deactivated, {whitelist_stats['errors']} errors")
            else:
                logger.info("✓ Whitelist file processed (no changes needed)")
            self.startup_checks["whitelist"] = True
        except FileNotFoundError:
            logger.info("✓ No whitelist.json file found (optional feature)")
            self.startup_checks["whitelist"] = True
        except Exception as e:
            error_msg = f"Whitelist sync failed: {str(e)}"
            logger.warning(f"⚠ {error_msg}")
            # Don't fail startup for whitelist issues
            self.startup_checks["whitelist"] = True
        
        # Log final status
        total_checks = len(self.startup_checks)
        passed_checks = sum(self.startup_checks.values())
        
        if passed_checks == total_checks and not self.startup_errors:
            logger.info(f"=== Startup Complete: {passed_checks}/{total_checks} checks passed ===")
        else:
            logger.warning(f"=== Startup Complete: {passed_checks}/{total_checks} checks passed, {len(self.startup_errors)} errors ===")
            for error in self.startup_errors:
                logger.error(f"  • {error}")
        
        return self.get_startup_status()
    
    def _validate_configuration(self):
        """Validate critical configuration settings"""
        errors = []
        
        # Check database URL
        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL not configured")
        
        # Check admin API key
        if not settings.ADMIN_API_KEY:
            errors.append("ADMIN_API_KEY not configured")
        
        # Check LNbits configuration if enabled
        if settings.LNBITS_ENABLED:
            if not settings.LNBITS_API_KEY:
                errors.append("LNBITS_API_KEY required when LNBITS_ENABLED=true")
            if not settings.LNBITS_URL:
                errors.append("LNBITS_URL required when LNBITS_ENABLED=true")
        
        # Check Nostr configuration if DM enabled
        if settings.NOSTR_DM_ENABLED:
            if not settings.NOSTR_PRIVATE_KEY:
                errors.append("NOSTR_PRIVATE_KEY required when NOSTR_DM_ENABLED=true")
            if not settings.NOSTR_RELAYS:
                errors.append("NOSTR_RELAYS required when NOSTR_DM_ENABLED=true")
        
        # Check if database file directory exists (for SQLite)
        if "sqlite" in settings.DATABASE_URL:
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if not os.path.exists(db_dir):
                errors.append(f"Database directory does not exist: {db_dir}")
            elif not os.access(db_dir, os.W_OK):
                errors.append(f"Database directory is not writable: {db_dir}")
        
        if errors:
            raise Exception("; ".join(errors))
    
    def get_startup_status(self) -> Dict[str, Any]:
        """Get current startup status"""
        return {
            "startup_time": self.startup_time.isoformat() if self.startup_time else None,
            "uptime_seconds": (datetime.utcnow() - self.startup_time).total_seconds() if self.startup_time else 0,
            "checks": self.startup_checks,
            "checks_passed": sum(self.startup_checks.values()),
            "total_checks": len(self.startup_checks),
            "errors": self.startup_errors,
            "status": "healthy" if all(self.startup_checks.values()) and not self.startup_errors else "degraded"
        }
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get detailed database information"""
        try:
            with engine.connect() as conn:
                db_info = {
                    "url": settings.DATABASE_URL.split("://")[0] + "://***",  # Hide credentials
                    "tables": {}
                }
                
                # Check users table
                if table_exists(conn, "users"):
                    user_columns = get_table_columns(conn, "users")
                    user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
                    active_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_active = 1")).scalar()
                    
                    db_info["tables"]["users"] = {
                        "exists": True,
                        "columns": len(user_columns),
                        "total_users": user_count,
                        "active_users": active_count
                    }
                else:
                    db_info["tables"]["users"] = {"exists": False}
                
                # Check invoices table
                if table_exists(conn, "invoices"):
                    invoice_columns = get_table_columns(conn, "invoices")
                    invoice_count = conn.execute(text("SELECT COUNT(*) FROM invoices")).scalar()
                    paid_count = conn.execute(text("SELECT COUNT(*) FROM invoices WHERE status = 'paid'")).scalar()
                    
                    db_info["tables"]["invoices"] = {
                        "exists": True,
                        "columns": len(invoice_columns),
                        "total_invoices": invoice_count,
                        "paid_invoices": paid_count
                    }
                else:
                    db_info["tables"]["invoices"] = {"exists": False}
                
                return db_info
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

# Global startup manager instance
startup_manager = StartupManager()

# Import necessary modules for database info
from sqlalchemy import text 