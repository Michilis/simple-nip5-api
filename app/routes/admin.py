from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models import User
from app.schemas import (
    AddUserRequest,
    RemoveUserRequest,
    SetUsernameRequest,
    RemoveUsernameRequest,
    UserResponse,
    StatusResponse,
    ErrorResponse
)
from app.services.nip05 import normalize_username, npub_to_pubkey, validate_npub, pubkey_to_npub
from app.services.nostr_sync import sync_username, nostr_sync_service
from app.services.nostr_dm import nostr_dm_service
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

@router.post(
    "/add", 
    response_model=StatusResponse,
    summary="Add User (Admin Only)",
    description="""
    Manually add a user to the NIP-05 whitelist.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Validates npub/pubkey format  
    2. If username not provided, generates temporary username and queues for Nostr profile sync
    3. Checks username availability
    4. Adds user to database
    5. User immediately appears in `/.well-known/nostr.json`
    
    ### Input Format:
    The `npub` field can accept either:
    - **npub format**: `npub1abc123...` (bech32 encoded)
    - **hex pubkey**: `abc123def456...` (64-character hex string)
    
    ### Use Cases:
    - **Admin-Only Mode**: Primary method for adding users
    - **Lightning Mode**: Manual overrides and free additions
    - **Testing**: Add test users without payment
    
    ### Username Rules (if provided):
    - Alphanumeric characters, dots, dashes, underscores only
    - Must start with alphanumeric character
    - 1-50 characters in length
    - If not provided, temporary username will be generated and real username fetched later
    """,
    responses={
        200: {
            "description": "User added successfully",
            "model": StatusResponse
        },
        400: {
            "description": "Invalid input format",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_npub": {
                            "summary": "Invalid npub format",
                            "value": {
                                "detail": "Invalid npub format"
                            }
                        },
                        "invalid_pubkey": {
                            "summary": "Invalid pubkey format",
                            "value": {
                                "detail": "Invalid pubkey format"
                            }
                        },
                        "invalid_input": {
                            "summary": "Invalid input format",
                            "value": {
                                "detail": "Invalid input format. Must be npub or 64-character hex pubkey"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid API key"
                    }
                }
            }
        },
        409: {
            "description": "Username or pubkey already exists",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "username_exists": {
                            "summary": "Username already taken",
                            "value": {
                                "detail": "Username already exists"
                            }
                        },
                        "pubkey_exists": {
                            "summary": "Pubkey already registered",
                            "value": {
                                "detail": "User with this pubkey already exists: alice"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def add_user(
    request: AddUserRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Add a user to the NIP-05 whitelist"""
    
    try:
        # Try to determine if input is npub or hex pubkey
        input_value = request.npub.strip()
        
        if input_value.startswith('npub1'):
            # Input is npub format
            if not validate_npub(input_value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid npub format"
                )
            pubkey = npub_to_pubkey(input_value)
            npub_value = input_value
        elif len(input_value) == 64:
            # Input is likely hex pubkey
            try:
                # Validate it's a valid hex string
                int(input_value, 16)
                pubkey = input_value.lower()
                npub_value = pubkey_to_npub(pubkey)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid pubkey format"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input format. Must be npub or 64-character hex pubkey"
            )
        
        # Check if user already exists by pubkey
        existing_user_by_pubkey = db.query(User).filter(User.pubkey == pubkey).first()
        if existing_user_by_pubkey:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with this pubkey already exists: {existing_user_by_pubkey.username}"
            )
        
        # Handle username - either provided or generate temporary one
        if request.username:
            # Username provided - validate and normalize it
            username = normalize_username(request.username)
            
            # Check if username already exists
            existing_user_by_username = db.query(User).filter(User.username == username).first()
            if existing_user_by_username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists"
                )
        else:
            # Username not provided - generate temporary username and queue for sync
            logger.info(f"No username provided, generating temporary username for pubkey {pubkey[:16]}...")
            
            # Generate temporary username from pubkey (first 8 chars + "tmp")
            temp_username = f"{pubkey[:8]}tmp"
            
            # Make sure temporary username is unique
            counter = 1
            original_temp = temp_username
            while db.query(User).filter(User.username == temp_username).first():
                temp_username = f"{original_temp}{counter}"
                counter += 1
            
            username = temp_username
            logger.info(f"Generated temporary username '{username}' - will sync from Nostr profile later")
        
        # Create new user  
        new_user = User(
            username=username,
            pubkey=pubkey,
            npub=npub_value,
            is_active=True,
            subscription_type="lifetime",  # Manually added users get lifetime subscription
            expires_at=None,  # Lifetime never expires
            last_synced_at=None,  # Will be queued for username sync if needed
            username_manual=bool(request.username)  # True if username provided, False if temporary
        )
        
        db.add(new_user)
        db.commit()
        
        # Send DM notification for whitelisting
        try:
            expires_at = "Never" if new_user.subscription_type == "lifetime" else new_user.expires_at.strftime("%Y-%m-%d") if new_user.expires_at else "Not set"
            await nostr_dm_service.send_dm(
                recipient_pubkey=pubkey,
                message_type="user_whitelisted", 
                username=username,
                expires_at=expires_at
            )
        except Exception as dm_error:
            logger.warning(f"Failed to send whitelist DM: {str(dm_error)}")
        
        # Create success message
        if request.username:
            message = f"User {username} added successfully"
        else:
            message = f"User added with temporary username '{username}'. Real username will be fetched from Nostr profile during next sync."
        
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

@router.post(
    "/remove", 
    response_model=StatusResponse,
    summary="Remove User (Admin Only)",
    description="""
    Remove a user from the NIP-05 whitelist.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Finds user by npub/pubkey
    2. Removes user from database
    3. User no longer appears in `/.well-known/nostr.json`
    
    ### Input Format:
    The `npub` field can accept either:
    - **npub format**: `npub1abc123...` (bech32 encoded)
    - **hex pubkey**: `abc123def456...` (64-character hex string)
    
    ### Important Notes:
    - This completely removes the user from the system
    - Any paid invoices for this user will become invalid
    - The username becomes available for re-registration
    """,
    responses={
        200: {
            "description": "User removed successfully",
            "model": StatusResponse
        },
        400: {
            "description": "Invalid npub or pubkey format",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_npub": {
                            "summary": "Invalid npub format",
                            "value": {
                                "detail": "Invalid npub format"
                            }
                        },
                        "invalid_pubkey": {
                            "summary": "Invalid pubkey format",
                            "value": {
                                "detail": "Invalid pubkey format"
                            }
                        },
                        "invalid_input": {
                            "summary": "Invalid input format",
                            "value": {
                                "detail": "Invalid input format. Must be npub or 64-character hex pubkey"
                            }
                        }
                    }
                }
            }
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
        # Try to determine if input is npub or hex pubkey
        input_value = request.npub.strip()
        
        if input_value.startswith('npub1'):
            # Input is npub format
            if not validate_npub(input_value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid npub format"
                )
            pubkey_hex = npub_to_pubkey(input_value)
        elif len(input_value) == 64:
            # Input is likely hex pubkey
            try:
                # Validate it's a valid hex string
                int(input_value, 16)
                pubkey_hex = input_value.lower()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid pubkey format"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input format. Must be npub or 64-character hex pubkey"
            )
        
        # Find user by pubkey
        user = db.query(User).filter(User.pubkey == pubkey_hex).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Store user info before deletion for DM
        user_pubkey = user.pubkey
        user_username = user.username
        
        db.delete(user)
        db.commit()
        
        # Send DM notification for removal
        try:
            await nostr_dm_service.send_dm(
                recipient_pubkey=user_pubkey,
                message_type="user_removed",
                username=user_username
            )
        except Exception as dm_error:
            logger.warning(f"Failed to send removal DM: {str(dm_error)}")
        
        return StatusResponse(
            status="success",
            message=f"User {user_username} removed successfully"
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
    summary="List Users (Admin Only)",
    description="""
    List all users in the system with optional filtering.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
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
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        }
    }
)
async def list_users(
    active_only: Optional[bool] = Query(False, description="Only return active users"),
    username: Optional[str] = Query(None, description="Filter by username (partial match)"),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """List users with optional filtering"""
    
    try:
        query = db.query(User)
        
        if active_only:
            query = query.filter(User.is_active == True)
        
        if username:
            query = query.filter(User.username.contains(username))
        
        users = query.order_by(User.created_at.desc()).all()
        
        return [
            UserResponse(
                id=user.id,
                username=user.username,
                pubkey=user.pubkey,
                npub=user.npub,
                is_active=user.is_active,
                subscription_type=user.subscription_type,
                expires_at=user.expires_at,
                created_at=user.created_at
            )
            for user in users
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )

@router.post(
    "/activate/{npub}", 
    response_model=StatusResponse,
    summary="Activate User (Admin Only)",
    description="""
    Activate a user (make them appear in nostr.json).
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### User Identifier
    The `{npub}` parameter can be either:
    - **npub format**: e.g., `npub1abc123...` (bech32 encoded)
    - **hex pubkey**: e.g., `abc123def456...` (64-character hex string)
    
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
    npub: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Activate a user"""
    
    try:
        user = find_user_by_identifier(db, npub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = True
        db.commit()
        
        # Send DM notification for activation  
        try:
            expires_at = "Never" if user.subscription_type == "lifetime" else user.expires_at.strftime("%Y-%m-%d") if user.expires_at else "Not set"
            await nostr_dm_service.send_dm(
                recipient_pubkey=user.pubkey,
                message_type="user_whitelisted",
                username=user.username,
                expires_at=expires_at
            )
        except Exception as dm_error:
            logger.warning(f"Failed to send activation DM: {str(dm_error)}")
        
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
    "/deactivate/{npub}", 
    response_model=StatusResponse,
    summary="Deactivate User (Admin Only)",
    description="""
    Deactivate a user (remove from nostr.json but keep in database).
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### User Identifier
    The `{npub}` parameter can be either:
    - **npub format**: e.g., `npub1abc123...` (bech32 encoded)
    - **hex pubkey**: e.g., `abc123def456...` (64-character hex string)
    
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
    npub: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Deactivate a user"""
    
    try:
        user = find_user_by_identifier(db, npub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = False
        db.commit()
        
        # Send DM notification for deactivation
        try:
            await nostr_dm_service.send_dm(
                recipient_pubkey=user.pubkey,
                message_type="user_removed",
                username=user.username
            )
        except Exception as dm_error:
            logger.warning(f"Failed to send deactivation DM: {str(dm_error)}")
        
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

@router.post(
    "/set-username", 
    response_model=StatusResponse,
    summary="Set Username Manually (Admin Only)",
    description="""
    Manually set a username for a user and disable automatic Nostr sync.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Finds user by npub/pubkey
    2. Validates and sets the new username
    3. Marks username as manually set
    4. Disables automatic Nostr profile sync for this user
    
    ### Input Format:
    - **npub**: Either npub format (`npub1abc123...`) or hex pubkey
    - **username**: Desired username (alphanumeric, dots, dashes, underscores only)
    
    ### Important Notes:
    - User will be excluded from automatic Nostr profile synchronization
    - Username must be unique and available
    - Use `/remove-username` to re-enable automatic sync
    """,
    responses={
        200: {
            "description": "Username set successfully",
            "model": StatusResponse
        },
        400: {
            "description": "Invalid input format",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_npub": {
                            "summary": "Invalid npub format",
                            "value": {
                                "detail": "Invalid npub format"
                            }
                        },
                        "invalid_username": {
                            "summary": "Invalid username format",
                            "value": {
                                "detail": "Invalid username format"
                            }
                        }
                    }
                }
            }
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
            "description": "Username already exists",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username already exists"
                    }
                }
            }
        }
    }
)
async def set_username_manually(
    request: SetUsernameRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Set a username manually and disable automatic sync"""
    
    try:
        # Find user by npub/pubkey
        user = find_user_by_identifier(db, request.npub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate and normalize username
        try:
            new_username = normalize_username(request.username)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid username format: {str(e)}"
            )
        
        # Check if username is already taken by another user
        existing_user = db.query(User).filter(
            User.username == new_username,
            User.id != user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        # Update user with manual username
        old_username = user.username
        user.username = new_username
        user.username_manual = True
        user.last_synced_at = datetime.utcnow()  # Mark as recently "synced" to avoid auto-sync
        
        db.commit()
        
        # Send DM notification for username update
        try:
            await nostr_dm_service.send_dm(
                recipient_pubkey=user.pubkey,
                message_type="username_updated",
                old_username=old_username,
                new_username=new_username
            )
        except Exception as dm_error:
            logger.warning(f"Failed to send username update DM: {str(dm_error)}")
        
        return StatusResponse(
            status="success",
            message=f"Username set to '{new_username}' manually. Automatic Nostr sync disabled for this user."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set username: {str(e)}"
        )

@router.post(
    "/remove-username", 
    response_model=StatusResponse,
    summary="Remove Manual Username (Admin Only)",
    description="""
    Remove manual username setting and re-enable automatic Nostr sync.
    
    **Admin Authentication Required** - Include `X-API-Key` header with your admin API key.
    
    ### Process:
    1. Finds user by npub/pubkey
    2. Removes manual username flag
    3. Re-enables automatic Nostr profile sync for this user
    4. User will be queued for username sync on next cycle
    
    ### Input Format:
    - **npub**: Either npub format (`npub1abc123...`) or hex pubkey
    
    ### Important Notes:
    - User will be included in automatic Nostr profile synchronization again
    - Username may change during next sync if Nostr profile has different name
    - Current username will be kept until next successful sync
    """,
    responses={
        200: {
            "description": "Manual username setting removed successfully",
            "model": StatusResponse
        },
        400: {
            "description": "Invalid npub format",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid npub format"
                    }
                }
            }
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
async def remove_username_manual(
    request: RemoveUsernameRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):
    """Remove manual username setting and re-enable automatic sync"""
    
    try:
        # Find user by npub/pubkey
        user = find_user_by_identifier(db, request.npub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove manual username flag and reset sync timestamp
        user.username_manual = False
        user.last_synced_at = None  # Queue for sync
        
        db.commit()
        
        return StatusResponse(
            status="success",
            message=f"Manual username setting removed for user '{user.username}'. Automatic Nostr sync re-enabled."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove manual username setting: {str(e)}"
        ) 