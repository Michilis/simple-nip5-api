import os
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Admin API security
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "your-secret-admin-key-here")
    
    # CORS configuration
    CORS_ENABLED: bool = os.getenv("CORS_ENABLED", "true").lower() == "true"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    CORS_ALLOW_METHODS: str = os.getenv("CORS_ALLOW_METHODS", "*")
    CORS_ALLOW_HEADERS: str = os.getenv("CORS_ALLOW_HEADERS", "*")
    
    # Nostr DM configuration
    NOSTR_DM_ENABLED: bool = os.getenv("NOSTR_DM_ENABLED", "true").lower() == "true"
    NOSTR_DM_PRIVATE_KEY: str = os.getenv("NOSTR_DM_PRIVATE_KEY", "")
    NOSTR_DM_RELAYS: str = os.getenv("NOSTR_DM_RELAYS", "wss://relay.damus.io,wss://nostr.bitcoiner.social,wss://relay.azzamo.net")
    NOSTR_DM_FROM_NAME: str = os.getenv("NOSTR_DM_FROM_NAME", "NIP-05 Service")
    MESSAGES_FILE: str = os.getenv("MESSAGES_FILE", "messages.json")
    
    # Whitelist configuration
    WHITELIST_FILE: str = os.getenv("WHITELIST_FILE", "whitelist.json")
    
    # LNbits configuration
    LNBITS_ENABLED: bool = os.getenv("LNBITS_ENABLED", "true").lower() == "true"
    LNBITS_API_KEY: str = os.getenv("LNBITS_API_KEY", "")
    LNBITS_ENDPOINT: str = os.getenv("LNBITS_ENDPOINT", "https://demo.lnbits.com")
    
    # NIP-05 pricing (in satoshis)
    NIP05_YEARLY_PRICE_SATS: int = int(os.getenv("NIP05_YEARLY_PRICE_SATS", "1000"))
    NIP05_LIFETIME_PRICE_SATS: int = int(os.getenv("NIP05_LIFETIME_PRICE_SATS", "5000"))
    
    # Invoice settings
    INVOICE_EXPIRY_SECONDS: int = int(os.getenv("INVOICE_EXPIRY_SECONDS", "1800"))  # 30 minutes
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./nip05.db")
    
    # Domain configuration
    DOMAIN: str = os.getenv("DOMAIN", "nip05.yourdomain.com")
    
    # Webhook URL for LNbits callbacks
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "http://localhost:8000/api/webhook/paid")
    
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
    
    # Default relays for NIP-05
    DEFAULT_RELAYS: List[str] = os.getenv(
        "NIP05_DEFAULT_RELAYS",
        "wss://relay.damus.io,wss://nostr.bitcoiner.social,wss://nostr.fmt.wiz.biz"
    ).split(",")

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property 
    def cors_methods_list(self) -> List[str]:
        """Convert CORS_ALLOW_METHODS string to list"""
        if self.CORS_ALLOW_METHODS == "*":
            return ["*"]
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(",") if method.strip()]
    
    @property
    def cors_headers_list(self) -> List[str]:
        """Convert CORS_ALLOW_HEADERS string to list"""
        if self.CORS_ALLOW_HEADERS == "*":
            return ["*"]
        return [header.strip() for header in self.CORS_ALLOW_HEADERS.split(",") if header.strip()]
    
    @property
    def nostr_dm_relays_list(self) -> List[str]:
        """Convert NOSTR_DM_RELAYS string to list"""
        return [relay.strip() for relay in self.NOSTR_DM_RELAYS.split(",") if relay.strip()]

# Global settings instance
settings = Settings() 