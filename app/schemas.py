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
        description="User's nostr public key in npub (bech32) format",
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
    username: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=50,
        description="Username to add (optional - will be fetched from Nostr profile if not provided)",
        example="bob"
    )
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format",
        example="npub1def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "bob",
                "npub": "npub1fa789c2c57agz7v5w90yesvf3myd5jakjzgz28w7jl8fvqchy6nqlu6rn6"
            }
        }

class RemoveUserRequest(BaseModel):
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format or hex pubkey format",
        example="npub1def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "npub": "npub1def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
            }
        }

class SetUsernameRequest(BaseModel):
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format or hex pubkey format",
        example="npub1fa789c2c57agz7v5w90yesvf3myd5jakjzgz28w7jl8fvqchy6nqlu6rn6"
    )
    username: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Username to set manually (alphanumeric, dots, dashes, underscores only)",
        example="alice"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "npub": "npub1fa789c2c57agz7v5w90yesvf3myd5jakjzgz28w7jl8fvqchy6nqlu6rn6",
                "username": "alice"
            }
        }

class RemoveUsernameRequest(BaseModel):
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format or hex pubkey format",
        example="npub1fa789c2c57agz7v5w90yesvf3myd5jakjzgz28w7jl8fvqchy6nqlu6rn6"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "npub": "npub1fa789c2c57agz7v5w90yesvf3myd5jakjzgz28w7jl8fvqchy6nqlu6rn6"
            }
        }

class UserInfoRequest(BaseModel):
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format or hex pubkey format",
        example="npub1p6xyr6u5vet33r4x724vxmp9uwfllax5zjdgxeujyrtxt90lp74qvah0rm"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "npub": "npub1p6xyr6u5vet33r4x724vxmp9uwfllax5zjdgxeujyrtxt90lp74qvah0rm"
            }
        }

class UserInfoResponse(BaseModel):
    pubkey: str = Field(
        ..., 
        description="User's nostr public key in hex format",
        example="0e8c41eb946657188ea6f2aac36c25e393fff4d4149a83679220d66595ff0faa"
    )
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format",
        example="npub1p6xyr6u5vet33r4x724vxmp9uwfllax5zjdgxeujyrtxt90lp74qvah0rm"
    )
    time_remaining: Optional[int] = Field(
        None,
        description="UTC timestamp when subscription expires (only shown if user is not whitelisted)",
        example=1704067200
    )
    is_whitelisted: bool = Field(
        ..., 
        description="Whether the user is currently whitelisted/active",
        example=True
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "pubkey": "0e8c41eb946657188ea6f2aac36c25e393fff4d4149a83679220d66595ff0faa",
                "npub": "npub1p6xyr6u5vet33r4x724vxmp9uwfllax5zjdgxeujyrtxt90lp74qvah0rm",
                "is_whitelisted": True
            }
        }

class UserResponse(BaseModel):
    id: int = Field(..., description="User's unique database ID", example=123)
    username: str = Field(..., description="User's NIP-05 username", example="alice")
    pubkey: str = Field(
        ..., 
        description="User's nostr public key in hex format",
        example="abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890"
    )
    npub: str = Field(
        ..., 
        description="User's nostr public key in npub (bech32) format",
        example="npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890"
    )
    is_active: bool = Field(..., description="Whether the user is active and appears in nostr.json", example=True)
    subscription_type: Optional[str] = Field(None, description="Subscription type (yearly/lifetime)", example="yearly")
    expires_at: Optional[datetime] = Field(
        None, 
        description="Subscription expiration timestamp (null for lifetime)",
        example="2025-01-01T12:00:00.000Z"
    )
    created_at: datetime = Field(
        ..., 
        description="User creation timestamp (ISO 8601)",
        example="2024-01-01T12:00:00.000Z"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "username": "alice",
                "pubkey": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
                "npub": "npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
                "is_active": True,
                "subscription_type": "yearly",
                "expires_at": "2025-01-01T12:00:00.000Z",
                "created_at": "2024-01-01T12:00:00.000Z"
            }
        }

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
    status: str = Field(
        ...,
        description="Operation status",
        example="success"
    )
    message: str = Field(
        ...,
        description="Human-readable status message",
        example="User alice added successfully"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "User alice added successfully"
            }
        }

# Error schemas
class ErrorResponse(BaseModel):
    error: str = Field(
        ...,
        description="Error type or category",
        example="ValidationError"
    )
    detail: Optional[str] = Field(
        None,
        description="Detailed error message",
        example="Username must start with alphanumeric character"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Username must start with alphanumeric character"
            }
        }

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
                    "create_invoice": "/api/invoice",
        "webhook": "/api/webhook/paid"
        }
    )
    documentation: str = Field(..., description="API documentation URL", example="/api-docs") 