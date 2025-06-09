from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict

from app.database import get_db
from app.models import User
from app.schemas import NostrJsonResponse
from app.services.nip05 import generate_nostr_json

router = APIRouter(tags=["nostr"])

@router.get("/.well-known/nostr.json", response_class=JSONResponse)
async def get_nostr_json(db: Session = Depends(get_db)):
    """Serve the NIP-05 nostr.json file with active users"""
    
    try:
        # Get all active users
        active_users = db.query(User).filter(User.is_active == True).all()
        
        # Build names dictionary: {username: pubkey}
        names_dict = {
            user.username: user.pubkey 
            for user in active_users
        }
        
        # Generate nostr.json response
        nostr_json = generate_nostr_json(names_dict)
        
        # Return JSON response with proper CORS headers
        response = JSONResponse(
            content=nostr_json,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "*",
                "Content-Type": "application/json"
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate nostr.json: {str(e)}"
        )