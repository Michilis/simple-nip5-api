from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User
from app.schemas import (
    AddUserRequest,
    RemoveUserRequest,
    UserResponse,
    StatusResponse,
    ErrorResponse
)
from app.services.nip05 import normalize_username, npub_to_pubkey, validate_npub
from app.services.nostr_sync import nostr_sync_service
from config import settings

router = APIRouter(prefix="/api/whitelist", tags=["admin"])

def verify_admin_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Verify admin API key"""
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return True

@router.post("/add", response_model=StatusResponse)
async def add_user(
    request: AddUserRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """Add user to whitelist (Admin only)"""
    
    try:
        # Validate and normalize inputs
        username = normalize_username(request.username)
        
        if not validate_npub(request.npub):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid npub format"
            )
        
        pubkey = npub_to_pubkey(request.npub)
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        
        if existing_user:
            # Update existing user
            existing_user.pubkey = pubkey
            existing_user.npub = request.npub
            existing_user.is_active = True
            message = f"User {username} updated successfully"
        else:
            # Create new user
            new_user = User(
                username=username,
                pubkey=pubkey,
                npub=request.npub,
                is_active=True
            )
            db.add(new_user)
            message = f"User {username} added successfully"
        
        db.commit()
        
        return StatusResponse(
            status="success",
            message=message
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add user: {str(e)}"
        )

@router.post("/remove", response_model=StatusResponse)
async def remove_user(
    request: RemoveUserRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """Remove user from whitelist (Admin only)"""
    
    try:
        username = normalize_username(request.username)
        
        # Find and remove user
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        db.delete(user)
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {username} removed successfully"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove user: {str(e)}"
        )

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """List all users in whitelist (Admin only)"""
    
    try:
        query = db.query(User)
        
        if active_only:
            query = query.filter(User.is_active == True)
        
        users = query.all()
        
        return [
            UserResponse(
                id=user.id,
                username=user.username,
                pubkey=user.pubkey,
                npub=user.npub,
                is_active=user.is_active,
                created_at=user.created_at
            )
            for user in users
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )

@router.post("/activate/{username}", response_model=StatusResponse)
async def activate_user(
    username: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """Activate a user (Admin only)"""
    
    try:
        normalized_username = normalize_username(username)
        
        user = db.query(User).filter(User.username == normalized_username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = True
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {normalized_username} activated successfully"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )

@router.post("/deactivate/{username}", response_model=StatusResponse)
async def deactivate_user(
    username: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """Deactivate a user (Admin only)"""
    
    try:
        normalized_username = normalize_username(username)
        
        user = db.query(User).filter(User.username == normalized_username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = False
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {normalized_username} deactivated successfully"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}"
        )

@router.post("/sync-usernames", response_model=StatusResponse)
async def manual_sync_usernames(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_key)
):
    """Manually trigger username synchronization (Admin only)"""
    
    if not settings.USERNAME_SYNC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username sync is disabled"
        )
    
    try:
        # Get users that need syncing
        users_to_sync = nostr_sync_service.get_users_to_sync(db)
        
        if not users_to_sync:
            return StatusResponse(
                status="success",
                message="No users need synchronization"
            )
        
        updates_count = 0
        errors_count = 0
        
        for user in users_to_sync:
            try:
                updated = await nostr_sync_service.sync_user_profile(user, db)
                if updated:
                    updates_count += 1
            except Exception:
                errors_count += 1
                continue
        
        message = f"Sync completed: {updates_count} updated, {errors_count} errors, {len(users_to_sync)} total"
        
        return StatusResponse(
            status="success",
            message=message
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync usernames: {str(e)}"
        ) 