from sqlalchemy import create_engine, Column, DateTime, String, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from config import settings

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

# Create all tables
def create_tables():
    """Create all tables and run migrations"""
    Base.metadata.create_all(bind=engine)
    
    # Run migration for subscription columns
    migrate_subscription_columns()

def migrate_subscription_columns():
    """Add subscription columns to existing users table if they don't exist"""
    try:
        # Create a connection to execute raw SQL
        with engine.connect() as conn:
            # Check if columns exist in users table
            result = conn.execute(text("SELECT * FROM users LIMIT 1"))
            columns = result.keys()
            
            # Add missing columns to users table
            if 'expires_at' not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN expires_at DATETIME;"))
                print("Added expires_at column to users table")
                
            if 'subscription_type' not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN subscription_type VARCHAR;"))
                print("Added subscription_type column to users table")
            
            # Check if columns exist in invoices table
            result = conn.execute(text("SELECT * FROM invoices LIMIT 1"))
            columns = result.keys()
            
            # Add missing columns to invoices table
            if 'subscription_type' not in columns:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN subscription_type VARCHAR;"))
                print("Added subscription_type column to invoices table")
            
            conn.commit()
                
    except Exception as e:
        print(f"Migration error (this may be normal for new installations): {e}") 