from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# Invoice Request/Response schemas
class InvoiceRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="Desired NIP-05 username")
    npub: str = Field(..., description="User's nostr public key in npub format")
    subscription_type: str = Field(..., description="Either 'yearly' or 'lifetime'")

class InvoiceResponse(BaseModel):
    payment_hash: str
    payment_request: str
    amount_sats: int
    expires_at: datetime
    username: str

# Admin schemas
class AddUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    npub: str = Field(..., description="User's nostr public key in npub format")

class RemoveUserRequest(BaseModel):
    username: str = Field(..., description="Username to remove")

class UserResponse(BaseModel):
    id: int
    username: str
    pubkey: str
    npub: str
    is_active: bool
    created_at: datetime

# Webhook schemas
class WebhookPayload(BaseModel):
    payment_hash: str
    paid: bool
    amount: int
    
# NIP-05 schemas
class NostrJsonResponse(BaseModel):
    names: Dict[str, str]
    
# Status schemas
class StatusResponse(BaseModel):
    status: str
    message: str

# Error schemas
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None 