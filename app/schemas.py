from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

# Invoice Request/Response schemas
class InvoiceRequest(BaseModel):
    username: str = Field(
        ..., 
        min_length=1, 
        max_length=50, 
        description="Desired NIP-05 username (alphanumeric, dots, dashes, underscores only)",
        example="alice"
    )
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) or hex format",
        example="npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890"
    )
    subscription_type: str = Field(
        ..., 
        description="Subscription duration type",
        example="yearly",
        pattern="^(yearly|lifetime)$"
    )
    years: int = Field(
        1,
        description="Number of years for yearly subscription (ignored for lifetime)",
        example=1,
        ge=1,
        le=10
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "alice",
                "npub": "npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
                "subscription_type": "yearly",
                "years": 1
            }
        }

class InvoiceResponse(BaseModel):
    payment_hash: str = Field(
        ...,
        description="Unique payment hash for this Lightning invoice",
        example="d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567"
    )
    payment_request: str = Field(
        ...,
        description="BOLT11 Lightning invoice payment request",
        example="lnbc10000n1p3xnhl2pp5d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567sp5zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zygs9qrsgq..."
    )
    amount_sats: int = Field(
        ...,
        description="Invoice amount in satoshis",
        example=1000
    )
    expires_at: datetime = Field(
        ...,
        description="Invoice expiration timestamp (ISO 8601)",
        example="2024-01-15T14:30:00.000Z"
    )
    username: str = Field(
        ...,
        description="Normalized username that will be registered",
        example="alice"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "payment_hash": "d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567",
                "payment_request": "lnbc10000n1p3xnhl2pp5d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567...",
                "amount_sats": 1000,
                "expires_at": "2024-01-15T14:30:00.000Z",
                "username": "alice"
            }
        }

# Admin schemas
class AddUserRequest(BaseModel):
    username: Optional[str] = None
    npub: str

class RemoveUserRequest(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: int
    username: str
    pubkey: str
    npub: Optional[str] = None
    is_active: bool
    subscription_type: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Webhook schemas
class WebhookPayload(BaseModel):
    payment_hash: str = Field(
        ...,
        description="Payment hash from the Lightning invoice",
        example="d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567"
    )
    paid: bool = Field(
        ...,
        description="Whether the payment has been confirmed",
        example=True
    )
    amount: int = Field(
        ...,
        description="Payment amount in satoshis",
        example=1000
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "payment_hash": "d63adcc3b6d2a7c6b5a8c9f2e1d3456789abcdef0123456789abcdef01234567",
                "paid": True,
                "amount": 1000
            }
        }
    
# NIP-05 schemas
class NostrJsonResponse(BaseModel):
    names: Dict[str, str] = Field(
        ...,
        description="Mapping of usernames to their hex public keys",
        example={
            "alice": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
            "bob": "def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
        }
    )
    relays: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Mapping of hex public keys to their recommended relay URLs",
        example={
            "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890": [
                "wss://relay.example.com",
                "wss://relay2.example.com"
            ]
        }
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "names": {
                    "alice": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
                    "bob": "def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
                },
                "relays": {
                    "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890": [
                        "wss://relay.example.com",
                        "wss://relay2.example.com"
                    ]
                }
            }
        }
    
# Status schemas
class StatusResponse(BaseModel):
    status: str
    message: str

# Error schemas
class ErrorResponse(BaseModel):
    detail: str

# Health check schemas
class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system health status", example="healthy")
    scheduler_running: bool = Field(..., description="Whether background scheduler is running", example=True)
    domain: str = Field(..., description="Configured domain for NIP-05 identities", example="nip05.yourdomain.com")
    features: Dict[str, bool] = Field(
        ...,
        description="Enabled/disabled feature flags",
        example={
            "lnbits_enabled": True,
            "username_sync_enabled": True,
            "admin_only_mode": False
        }
    )
    endpoints: Dict[str, str] = Field(
        ...,
        description="Available API endpoints based on enabled features",
        example={
            "nostr_json": "/.well-known/nostr.json",
            "create_invoice": "/api/public/invoice",
            "webhook": "/api/public/webhook/paid"
        }
    )
    documentation: str = Field(..., description="API documentation URL", example="/api-docs")

class UserCreate(BaseModel):
    pubkey: str
    username: Optional[str] = None
    is_active: bool = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    is_active: Optional[bool] = None 