from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import NostrJsonResponse
from config import settings

router = APIRouter(tags=["nostr"])

@router.get(
    "/.well-known/nostr.json",
    response_model=NostrJsonResponse,
    summary="NIP-05 Identity Resolution",
    description="""
    **The core NIP-05 endpoint** that resolves usernames to Nostr public keys.
    
    This endpoint is the heart of the NIP-05 identity system. It returns a JSON object
    mapping usernames to their corresponding hex-format public keys.
    
    ### How NIP-05 Works:
    1. User claims identity: `alice@yourdomain.com`
    2. Nostr clients query: `https://yourdomain.com/.well-known/nostr.json`
    3. Client finds mapping: `"alice": "abc123..."`
    4. Client verifies the public key matches
    
    ### Response Format:
    Standard NIP-05 JSON structure with `names` object containing username→pubkey mappings.
    
    **Only active users appear in this response.**
    
    ### CORS Headers:
    This endpoint includes appropriate CORS headers for cross-origin access by Nostr clients.
    
    ### Caching:
    Consider implementing caching for this endpoint in production for better performance.
    """,
    responses={
        200: {
            "description": "NIP-05 identity mappings",
            "model": NostrJsonResponse,
            "content": {
                "application/json": {
                    "example": {
                        "names": {
                            "alice": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890",
                            "bob": "def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890abc123"
                        }
                    }
                }
            }
        }
    }
)
async def nostr_json(db: Session = Depends(get_db)):
    """
    NIP-05 identity resolution endpoint
    
    Returns mapping of usernames to their hex public keys for active users only.
    This is the standard endpoint that Nostr clients query to resolve NIP-05 identities.
    """
    
    # Get all active users
    users = db.query(User).filter(User.is_active == True).all()
    
    # Build names mapping
    names = {user.username: user.pubkey for user in users}
    
    # Return with CORS headers
    response = JSONResponse(
        content={"names": names},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Cache-Control": "public, max-age=300"  # Cache for 5 minutes
        }
    )
    
    return response