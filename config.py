import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Admin API security
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "your-secret-admin-key-here")
    
    # LNbits configuration
    LNBITS_ENABLED: bool = os.getenv("LNBITS_ENABLED", "true").lower() == "true"
    LNBITS_API_KEY: str = os.getenv("LNBITS_API_KEY", "")
    LNBITS_ENDPOINT: str = os.getenv("LNBITS_ENDPOINT", "https://demo.lnbits.com")
    
    # NIP-05 pricing (in satoshis)
    NIP05_YEARLY_PRICE_SATS: int = int(os.getenv("NIP05_YEARLY_PRICE_SATS", "1000"))
    NIP05_LIFETIME_PRICE_SATS: int = int(os.getenv("NIP05_LIFETIME_PRICE_SATS", "10000"))
    
    # Invoice settings
    INVOICE_EXPIRY_SECONDS: int = int(os.getenv("INVOICE_EXPIRY_SECONDS", "1800"))  # 30 minutes
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./nip05.db")
    
    # Domain configuration
    DOMAIN: str = os.getenv("DOMAIN", "localhost")
    
    # Webhook URL for LNbits callbacks
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "http://localhost:8000/api/public/webhook/paid")
    
    # Polling configuration
    POLL_INITIAL_INTERVAL: int = int(os.getenv("POLL_INITIAL_INTERVAL", "60"))  # 1 minute
    POLL_LATER_INTERVAL: int = int(os.getenv("POLL_LATER_INTERVAL", "300"))     # 5 minutes
    POLL_MAX_TIME: int = int(os.getenv("POLL_MAX_TIME", "1800"))                # 30 minutes
    POLL_SWITCH_TIME: int = int(os.getenv("POLL_SWITCH_TIME", "600"))           # 10 minutes
    
    # Username sync configuration
    USERNAME_SYNC_ENABLED: bool = os.getenv("USERNAME_SYNC_ENABLED", "true").lower() == "true"
    USERNAME_SYNC_INTERVAL_MINUTES: int = int(os.getenv("USERNAME_SYNC_INTERVAL_MINUTES", "15"))
    USERNAME_SYNC_MAX_AGE_HOURS: int = int(os.getenv("USERNAME_SYNC_MAX_AGE_HOURS", "24"))
    NOSTR_RELAYS: str = os.getenv("NOSTR_RELAYS", "wss://relay.azzamo.net,wss://relay.damus.io,wss://primal.net")

# Global settings instance
settings = Settings() 