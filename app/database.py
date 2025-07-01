from sqlalchemy import create_engine, Column, DateTime, String, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from config import settings
import logging

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency to get database session
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_table_columns(conn, table_name: str) -> list:
    """Get list of column names for a table"""
    try:
        if "sqlite" in settings.DATABASE_URL:
            # SQLite specific query
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result]  # Column name is at index 1
            return columns
        else:
            # PostgreSQL/MySQL compatible approach
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return columns
    except Exception as e:
        logger.debug(f"Error getting columns for {table_name}: {e}")
        return []

def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists"""
    try:
        if "sqlite" in settings.DATABASE_URL:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"
            ), {"table_name": table_name})
            return result.fetchone() is not None
        else:
            inspector = inspect(engine)
            return table_name in inspector.get_table_names()
    except Exception as e:
        logger.error(f"Error checking if table {table_name} exists: {e}")
        return False

def add_column_if_not_exists(conn, table_name: str, column_name: str, column_definition: str):
    """Add a column to a table if it doesn't already exist"""
    try:
        columns = get_table_columns(conn, table_name)
        if column_name not in columns:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            conn.execute(text(sql))
            logger.info(f"Added {column_name} column to {table_name} table")
            return True
        else:
            logger.debug(f"Column {column_name} already exists in {table_name}")
            return False
    except Exception as e:
        logger.error(f"Error adding column {column_name} to {table_name}: {e}")
        raise

def run_database_migrations():
    """Run all database migrations"""
    migration_count = 0
    
    try:
        # Create a connection to execute raw SQL
        with engine.connect() as conn:
            # Start a transaction
            trans = conn.begin()
            
            try:
                logger.info("Running database migrations...")
                
                # Check if users table exists
                if table_exists(conn, "users"):
                    # Add missing columns to users table
                    if add_column_if_not_exists(conn, "users", "expires_at", "DATETIME"):
                        migration_count += 1
                    
                    if add_column_if_not_exists(conn, "users", "subscription_type", "VARCHAR"):
                        migration_count += 1
                    
                    if add_column_if_not_exists(conn, "users", "note", "VARCHAR"):
                        migration_count += 1
                    
                    if add_column_if_not_exists(conn, "users", "username_manual", "BOOLEAN DEFAULT FALSE"):
                        migration_count += 1
                else:
                    logger.info("Users table does not exist yet - will be created by SQLAlchemy")
                
                # Check if invoices table exists
                if table_exists(conn, "invoices"):
                    # Add missing columns to invoices table
                    if add_column_if_not_exists(conn, "invoices", "subscription_type", "VARCHAR"):
                        migration_count += 1
                else:
                    logger.info("Invoices table does not exist yet - will be created by SQLAlchemy")
                
                # Commit the transaction
                trans.commit()
                
                if migration_count > 0:
                    logger.info(f"Database migrations completed: {migration_count} columns added")
                else:
                    logger.info("Database schema is up to date")
                    
            except Exception as e:
                # Rollback on error
                trans.rollback()
                logger.error(f"Database migration failed, rolling back: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Database migration error: {e}")
        raise

def verify_database_schema():
    """Verify that the database schema matches the expected structure"""
    try:
        with engine.connect() as conn:
            # Check users table
            if table_exists(conn, "users"):
                user_columns = get_table_columns(conn, "users")
                required_user_columns = [
                    'id', 'username', 'pubkey', 'npub', 'is_active', 
                    'created_at', 'last_synced_at', 'expires_at', 
                    'subscription_type', 'note', 'username_manual'
                ]
                
                missing_columns = [col for col in required_user_columns if col not in user_columns]
                if missing_columns:
                    logger.error(f"Missing columns in users table: {missing_columns}")
                    return False
                else:
                    logger.info("Users table schema verified successfully")
            
            # Check invoices table
            if table_exists(conn, "invoices"):
                invoice_columns = get_table_columns(conn, "invoices")
                required_invoice_columns = [
                    'id', 'payment_hash', 'payment_request', 'amount_sats',
                    'status', 'username', 'pubkey', 'npub', 'subscription_type',
                    'poll_attempts', 'next_poll_time', 'created_at', 
                    'paid_at', 'expires_at', 'user_id'
                ]
                
                missing_columns = [col for col in required_invoice_columns if col not in invoice_columns]
                if missing_columns:
                    logger.error(f"Missing columns in invoices table: {missing_columns}")
                    return False
                else:
                    logger.info("Invoices table schema verified successfully")
            
            return True
            
    except Exception as e:
        logger.error(f"Database schema verification failed: {e}")
        return False

# Create all tables
def create_tables():
    """Create all tables and run migrations"""
    try:
        logger.info("Creating database tables...")
        
        # Create tables from SQLAlchemy models
        Base.metadata.create_all(bind=engine)
        logger.info("SQLAlchemy tables created successfully")
        
        # Run migrations for additional columns
        run_database_migrations()
        
        # Verify schema
        if verify_database_schema():
            logger.info("Database initialization completed successfully")
        else:
            raise Exception("Database schema verification failed")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Legacy function name for backward compatibility
def migrate_subscription_columns():
    """Legacy function - use create_tables() instead"""
    logger.warning("migrate_subscription_columns() is deprecated, use create_tables() instead")
    run_database_migrations() 