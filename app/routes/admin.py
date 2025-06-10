from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import logging

from app.database import get_db
from app.models import User, Invoice
from app.schemas import (
    AddUserRequest,
    RemoveUserRequest,
    UserResponse,
    StatusResponse,
    ErrorResponse,
    UserCreate,
    UserUpdate
)
from app.services.nip05 import normalize_username, npub_to_pubkey, validate_npub, is_hex_pubkey
from app.services.nostr_sync import fetch_nostr_profile, sync_username
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whitelist", tags=["admin"])

def verify_admin_key(x_api_key: str = Header(..., description="Admin API key for authentication")):
    """Verify admin API key"""
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key

def find_user_by_identifier(db: Session, identifier: str) -> Optional[User]:
    """Find user by username, npub, or pubkey"""
    
    # First try to normalize as username
    try:
        normalized_username = normalize_username(identifier)
        user = db.query(User).filter(User.username == normalized_username).first()
        if user:
            return user
    except ValueError:
        pass  # Not a valid username format
    
    # Try as npub
    if identifier.startswith('npub1') and validate_npub(identifier):
        try:
            pubkey = npub_to_pubkey(identifier)
            user = db.query(User).filter(User.pubkey == pubkey).first()
            if user:
                return user
        except:
            pass
    
    # Try as hex pubkey (64 character hex string)
    if len(identifier) == 64:
        try:
            # Validate it's a hex string
            int(identifier, 16)
            user = db.query(User).filter(User.pubkey == identifier).first()
            if user:
                return user
        except ValueError:
            pass
    
    return None

async def get_username_from_nostr(pubkey: str) -> str:
    """Get username from Nostr profile or return a fallback."""
    try:
        profile = await fetch_nostr_profile(pubkey)
        if profile and 'name' in profile and profile['name']:
            return profile['name']
    except Exception as e:
        logger.error(f"Error fetching Nostr profile: {str(e)}")
    
    # Fallback to first 8 chars of pubkey
    return f"user_{pubkey[:8]}"

@router.post(
    "/add",
    response_model=StatusResponse,
    summary="Add User to Whitelist",
    description="""
    Add a user to the NIP-05 whitelist.
    
    ### Request Body:
    - **username**: Optional username. If not provided, will be fetched from Nostr profile
    - **npub**: User's nostr public key in npub (bech32) or hex format
    
    ### Notes:
    - If username is not provided, it will be fetched from the user's Nostr profile
    - If profile fetch fails, first 16 characters of pubkey will be used as username
    - Public key can be provided in either npub (bech32) or hex format
    - User will appear in `/.well-known/nostr.json` immediately
    
    ### Example Request (with username):
    ```json
    {
        "username": "alice",
        "npub": "npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890"
    }
    ```
    
    ### Example Request (without username):
    ```json
    {
        "npub": "npub1abc123def456ghi789jkl012mno345pqr678stu901vwx234yzab567cdef890"
    }
    ```
    """,
    responses={
        200: {
            "description": "User added successfully",
            "model": StatusResponse
        },
        400: {
            "description": "Invalid request parameters",
            "model": ErrorResponse
        },
        409: {
            "description": "Username already taken",
            "model": ErrorResponse
        },
        401: {
            "description": "Invalid API key",
            "model": ErrorResponse
        }
    }
)
async def add_user(
    request: AddUserRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key)
):
    """Add a user to the NIP-05 whitelist"""
    
    try:
        # Handle both npub and hex pubkey formats
        if is_hex_pubkey(request.npub):
            pubkey = request.npub
            npub = None  # We don't store npub if only hex was provided
        else:
            try:
                pubkey = npub_to_pubkey(request.npub)
                npub = request.npub
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid public key format. Must be npub (bech32) or hex format"
                )
        
        # Check if pubkey is already registered
        existing_pubkey = db.query(User).filter(User.pubkey == pubkey).first()
        if existing_pubkey:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Public key already registered"
            )
        
        # Get username (either from request or Nostr profile)
        if request.username:
            username = normalize_username(request.username)
        else:
            username = await get_username_from_nostr(pubkey)
        
        # Check if username is already taken
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )
        
        # Create new user
        new_user = User(
            username=username,
            pubkey=pubkey,
            npub=npub,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        
        # Sync username in background
        background_tasks = BackgroundTasks()
        background_tasks.add_task(sync_username, [new_user])
        
        return StatusResponse(
            status="success",
            message=f"User {username} added successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add user: {str(e)}"
        )

@router.post(
    "/remove", 
    response_model=StatusResponse,
    summary="Remove User (Admin Only)",
    description="""
    Remove a user from the NIP-05 whitelist.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Finds user by username
    2. Removes user from database
    3. User no longer appears in `/.well-known/nostr.json`
    
    ### Important Notes:
    - This completely removes the user from the system
    - Any paid invoices for this username will become invalid
    - The username becomes available for re-registration
    """,
    responses={
        200: {
            "description": "User removed successfully",
            "model": StatusResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User not found"
                    }
                }
            }
        }
    }
)
async def remove_user(
    request: RemoveUserRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Remove a user from the NIP-05 whitelist"""
    
    try:
        username = normalize_username(request.username)
        
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
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove user: {str(e)}"
        )

@router.get(
    "/users", 
    response_model=List[UserResponse],
    summary="List Users",
    description="""
    List all users in the system with optional filtering.
    
    ### Query Parameters:
    - **active_only**: If `true`, only returns active users (those appearing in nostr.json)
    - **username**: Filter by specific username (partial matches supported)
    
    ### Response Fields:
    - **id**: Database ID
    - **username**: NIP-05 username
    - **pubkey**: Hex format public key
    - **npub**: Bech32 format public key
    - **is_active**: Whether user appears in nostr.json
    - **subscription_type**: Subscription type
    - **expires_at**: Subscription expiration date
    - **created_at**: User creation timestamp
    """,
    responses={
        200: {
            "description": "List of users",
            "model": List[UserResponse]
        }
    },
    tags=["public"]
)
async def list_users(
    active_only: Optional[bool] = Query(False, description="Only return active users"),
    username: Optional[str] = Query(None, description="Filter by username (partial match)"),
    db: Session = Depends(get_db)
):
    """List all users with optional filtering"""
    try:
        query = db.query(User)
        
        # Apply filters
        if active_only:
            query = query.filter(User.is_active == True)
        if username:
            query = query.filter(User.username.ilike(f"%{username}%"))
        
        # Get users
        users = query.all()
        
        return users
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )

@router.get(
    "/users/{pubkey}",
    response_model=UserResponse,
    summary="Get User Details",
    description="""
    Get detailed information about a specific user.
    
    ### Path Parameters:
    - **pubkey**: User's public key in hex format
    
    ### Response Fields:
    - **id**: Database ID
    - **username**: NIP-05 username
    - **pubkey**: Hex format public key
    - **npub**: Bech32 format public key
    - **is_active**: Whether user appears in nostr.json
    - **subscription_type**: Subscription type
    - **expires_at**: Subscription expiration date
    - **created_at**: User creation timestamp
    """,
    responses={
        200: {
            "description": "User details",
            "model": UserResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse
        }
    },
    tags=["public"]
)
async def get_user(
    pubkey: str,
    db: Session = Depends(get_db)
):
    """Get user details by public key"""
    try:
        user = db.query(User).filter(User.pubkey == pubkey).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )

@router.put(
    "/users/{pubkey}",
    response_model=UserResponse,
    summary="Update User (Admin Only)",
    description="""
    Update a user's details.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Path Parameters:
    - **pubkey**: User's public key in hex format
    
    ### Request Body:
    - **username**: Optional new username
    - **is_active**: Optional active status
    
    ### Notes:
    - Only provided fields will be updated
    - Username must be unique if changed
    """,
    responses={
        200: {
            "description": "User updated successfully",
            "model": UserResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse
        },
        409: {
            "description": "Username already taken",
            "model": ErrorResponse
        }
    }
)
async def update_user(
    pubkey: str,
    user_update: UserUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Update user details (admin only)"""
    try:
        user = db.query(User).filter(User.pubkey == pubkey).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update fields if provided
        if user_update.username is not None:
            # Check if new username is taken
            existing = db.query(User).filter(User.username == user_update.username).first()
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken"
                )
            user.username = user_update.username
            
        if user_update.is_active is not None:
            user.is_active = user_update.is_active
        
        db.commit()
        
        # Sync username in background if changed
        if user_update.username is not None:
            background_tasks.add_task(sync_username, [user])
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.delete(
    "/users/{pubkey}",
    response_model=StatusResponse,
    summary="Delete User (Admin Only)",
    description="""
    Delete a user from the system.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Path Parameters:
    - **pubkey**: User's public key in hex format
    
    ### Notes:
    - This completely removes the user from the system
    - Any paid invoices for this username will become invalid
    - The username becomes available for re-registration
    """,
    responses={
        200: {
            "description": "User deleted successfully",
            "model": StatusResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse
        }
    }
)
async def delete_user(
    pubkey: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Delete a user (admin only)"""
    try:
        user = db.query(User).filter(User.pubkey == pubkey).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        db.delete(user)
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {user.username} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.post(
    "/activate/{username}", 
    response_model=StatusResponse,
    summary="Activate User (Admin Only)",
    description="""
    Activate a user (make them appear in nostr.json).
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### User Identifier
    The `{username}` parameter can be any of:
    - **Username**: e.g., `alice` 
    - **npub**: e.g., `npub1abc123...`
    - **Pubkey**: 64-character hex string, e.g., `abc123def456...`
    
    ### Use Cases:
    - Re-enabling previously deactivated users
    - Manually activating users added with is_active=false
    """,
    responses={
        200: {
            "description": "User activated successfully",
            "model": StatusResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse
        }
    }
)
async def activate_user(
    username: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Activate a user"""
    
    try:
        user = find_user_by_identifier(db, username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = True
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {user.username} activated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )

@router.post(
    "/deactivate/{username}", 
    response_model=StatusResponse,
    summary="Deactivate User (Admin Only)",
    description="""
    Deactivate a user (remove from nostr.json but keep in database).
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### User Identifier
    The `{username}` parameter can be any of:
    - **Username**: e.g., `alice` 
    - **npub**: e.g., `npub1abc123...`
    - **Pubkey**: 64-character hex string, e.g., `abc123def456...`
    
    ### Difference from Remove:
    - **Deactivate**: User stays in database but doesn't appear in nostr.json
    - **Remove**: User is completely deleted from database
    
    ### Use Cases:
    - Temporarily suspending users
    - Keeping user records while disabling service
    """,
    responses={
        200: {
            "description": "User deactivated successfully",
            "model": StatusResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "User not found",
            "model": ErrorResponse
        }
    }
)
async def deactivate_user(
    username: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Deactivate a user"""
    
    try:
        user = find_user_by_identifier(db, username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = False
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"User {user.username} deactivated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}"
        )

@router.post(
    "/sync-usernames", 
    response_model=StatusResponse,
    summary="Sync Usernames from Nostr (Admin Only)",
    description="""
    Manually trigger username synchronization from Nostr profiles.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Queries all active users needing sync (24+ hours since last sync)
    2. Connects to Nostr relays via WebSocket
    3. Fetches kind:0 (profile) events for each user
    4. Extracts `name` field from profile metadata
    5. Updates username if different and available
    
    ### Automatic Sync:
    This process also runs automatically every 15 minutes in the background
    when `USERNAME_SYNC_ENABLED=true`.
    
    ### Rate Limiting:
    - Max once per 24 hours per user
    - Checks multiple Nostr relays for reliability
    - Validates usernames before updating
    """,
    responses={
        200: {
            "description": "Username sync completed",
            "model": StatusResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        503: {
            "description": "Username sync disabled",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username sync is disabled"
                    }
                }
            }
        }
    }
)
async def sync_usernames(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Manually trigger username sync from Nostr profiles"""
    
    if not settings.USERNAME_SYNC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Username sync is disabled"
        )
    
    try:
        # Get users that need syncing
        max_age = datetime.utcnow() - timedelta(hours=settings.USERNAME_SYNC_MAX_AGE_HOURS)
        
        users_to_sync = db.query(User).filter(
            User.is_active == True,
            (User.last_synced_at == None) | (User.last_synced_at < max_age)
        ).all()
        
        if not users_to_sync:
            return StatusResponse(
                status="success",
                message="No users need syncing at this time"
            )
        
        # Schedule sync as background task
        background_tasks.add_task(sync_username, users_to_sync)
        
        return StatusResponse(
            status="success",
            message=f"Started username sync for {len(users_to_sync)} users"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start username sync: {str(e)}"
        )

@router.post("/users", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Create a new user (admin only)."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.pubkey == user.pubkey).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Get username from Nostr if not provided
    username = user.username
    if not username:
        username = await get_username_from_nostr(user.pubkey)
    
    # Create new user
    db_user = User(
        pubkey=user.pubkey,
        username=username,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Sync username in background
    background_tasks.add_task(sync_username, [db_user])
    
    return db_user 