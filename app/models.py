from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    pubkey = Column(String, nullable=False)  # hex format
    npub = Column(String, nullable=False)    # bech32 format
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)  # Track Nostr profile sync
    
    # Subscription management
    expires_at = Column(DateTime, nullable=True)  # When subscription expires
    subscription_type = Column(String, nullable=True)  # yearly, lifetime, whitelist
    
    # Admin notes (for whitelist entries)
    note = Column(String, nullable=True)  # Optional admin note
    
    # Manual username management
    username_manual = Column(Boolean, default=False)  # True if username was set manually
    
    # Relationship to invoices
    invoices = relationship("Invoice", back_populates="user")

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    payment_hash = Column(String, unique=True, index=True, nullable=False)
    payment_request = Column(String, nullable=False)  # Lightning invoice/BOLT11
    amount_sats = Column(Integer, nullable=False)
    status = Column(String, default="unpaid")  # unpaid, paid, expired
    username = Column(String, nullable=False)
    pubkey = Column(String, nullable=False)
    npub = Column(String, nullable=False)
    subscription_type = Column(String, nullable=False)  # yearly, lifetime
    
    # Polling metadata
    poll_attempts = Column(Integer, default=0)
    next_poll_time = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    
    # Foreign key to user (optional, for paid invoices)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="invoices") 