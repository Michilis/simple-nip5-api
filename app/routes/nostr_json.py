from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime

from app.database import get_db
from app.models import User
from app.schemas import NostrJsonResponse
from app.services.nip05 import npub_to_pubkey
from config import settings

router = APIRouter()

@router.get(
    "/.well-known/nostr.json",
    response_model=NostrJsonResponse,
    summary="NIP-05 Identity Verification",
    description="""
    NIP-05 identity verification endpoint.
    
    Returns a mapping of usernames to their hex public keys.
    Also includes recommended relay information.
    
    ### Query Parameters:
    - **name**: Optional username to filter results
    
    ### Response Format:
    ```json
    {
      "names": {
        "username": "hex_pubkey"
      },
      "relays": {
        "hex_pubkey": ["relay_url1", "relay_url2"]
      }
    }
    ```
    
    ### Special Cases:
    - `_@domain` is treated as the root identifier
    - All pubkeys are returned in hex format
    - CORS headers are included for JavaScript access
    """,
    responses={
        200: {
            "description": "NIP-05 identity mapping",
            "model": NostrJsonResponse
        }
    }
)
async def nostr_json(
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    response: Response = None
):
    """NIP-05 identity verification endpoint"""
    
    try:
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        # Get active users
        query = db.query(User).filter(User.is_active == True)
        
        # Handle _@domain special case
        if name == "_":
            # Return all users
            users = query.all()
        elif name:
            # Filter by username
            users = query.filter(User.username == name).all()
        else:
            # Return all users
            users = query.all()
        
        # Build names mapping
        names = {}
        relays = {}
        
        # Get default relay list from settings
        default_relays = settings.DEFAULT_RELAYS if hasattr(settings, 'DEFAULT_RELAYS') else []
        
        for user in users:
            # Convert npub to hex pubkey
            hex_pubkey = npub_to_pubkey(user.npub)
            
            # Add to names mapping
            names[user.username] = hex_pubkey
            
            # Add to relays mapping if we have relays
            if default_relays:
                relays[hex_pubkey] = default_relays
        
        return NostrJsonResponse(
            names=names,
            relays=relays if relays else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate NIP-05 response: {str(e)}"
        )