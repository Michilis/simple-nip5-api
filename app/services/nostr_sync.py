import asyncio
import json
import logging
import websockets
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.services.nip05 import normalize_username
from config import settings

logger = logging.getLogger(__name__)

class NostrSyncService:
    def __init__(self):
        self.relays = [relay.strip() for relay in settings.NOSTR_RELAYS.split(',') if relay.strip()]
        self.timeout = 10  # WebSocket timeout in seconds
        
    async def fetch_user_profile(self, pubkey: str) -> Optional[Dict]:
        """Fetch user profile (kind:0) from Nostr relays"""
        
        for relay_url in self.relays:
            try:
                profile = await self._query_relay(relay_url, pubkey)
                if profile:
                    logger.info(f"Retrieved profile for {pubkey[:8]}... from {relay_url}")
                    return profile
                    
            except Exception as e:
                logger.warning(f"Failed to query relay {relay_url}: {str(e)}")
                continue
        
        logger.warning(f"Could not retrieve profile for {pubkey[:8]}... from any relay")
        return None
    
    async def _query_relay(self, relay_url: str, pubkey: str) -> Optional[Dict]:
        """Query a single relay for user profile"""
        
        # Nostr REQ message for kind:0 (profile metadata)
        req_message = json.dumps([
            "REQ",
            "sync",
            {
                "kinds": [0],
                "authors": [pubkey],
                "limit": 1
            }
        ])
        
        try:
            async with websockets.connect(
                relay_url, 
                timeout=self.timeout,
                ping_interval=None
            ) as websocket:
                
                # Send the request
                await websocket.send(req_message)
                logger.debug(f"Sent profile request for {pubkey[:8]}... to {relay_url}")
                
                # Wait for response
                timeout_time = asyncio.get_event_loop().time() + self.timeout
                
                while asyncio.get_event_loop().time() < timeout_time:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        response = json.loads(message)
                        
                        # Check if this is an EVENT response
                        if response[0] == "EVENT" and len(response) >= 3:
                            event = response[2]
                            
                            # Validate event structure
                            if (event.get("kind") == 0 and 
                                event.get("pubkey") == pubkey and 
                                "content" in event):
                                
                                try:
                                    # Parse the profile content
                                    profile_data = json.loads(event["content"])
                                    return profile_data
                                except json.JSONDecodeError:
                                    logger.warning(f"Invalid JSON in profile content for {pubkey[:8]}...")
                                    continue
                        
                        # Check for EOSE (End of Stored Events)
                        elif response[0] == "EOSE":
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.debug(f"WebSocket error with {relay_url}: {str(e)}")
            raise
        
        return None
    
    def extract_username_from_profile(self, profile_data: Dict) -> Optional[str]:
        """Extract and validate username from profile data"""
        
        try:
            # Get the 'name' field from profile
            name = profile_data.get("name", "").strip()
            
            if not name:
                logger.debug("No name field in profile or empty")
                return None
            
            # Validate and normalize the name
            try:
                normalized_name = normalize_username(name)
                return normalized_name
            except ValueError as e:
                logger.debug(f"Invalid name '{name}': {str(e)}")
                return None
                
        except Exception as e:
            logger.warning(f"Error extracting username from profile: {str(e)}")
            return None
    
    async def sync_user_profile(self, user: User, db: Session) -> bool:
        """Sync a single user's profile from Nostr"""
        
        try:
            logger.info(f"Syncing profile for user {user.username} ({user.pubkey[:8]}...)")
            
            # Fetch profile from relays
            profile_data = await self.fetch_user_profile(user.pubkey)
            
            if not profile_data:
                # Update sync timestamp even if no profile found
                user.last_synced_at = datetime.utcnow()
                db.commit()
                return False
            
            # Extract username from profile
            new_username = self.extract_username_from_profile(profile_data)
            
            if not new_username:
                logger.info(f"No valid username found in profile for {user.username}")
                user.last_synced_at = datetime.utcnow()
                db.commit()
                return False
            
            # Check if username needs updating
            if new_username != user.username:
                # Check if new username is already taken
                existing_user = db.query(User).filter(
                    User.username == new_username,
                    User.id != user.id
                ).first()
                
                if existing_user:
                    logger.warning(f"Username '{new_username}' already taken, cannot update {user.username}")
                    user.last_synced_at = datetime.utcnow()
                    db.commit()
                    return False
                
                # Update username
                old_username = user.username
                user.username = new_username
                user.last_synced_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Updated username: '{old_username}' → '{new_username}'")
                return True
            else:
                # Username unchanged, just update sync timestamp
                user.last_synced_at = datetime.utcnow()
                db.commit()
                logger.debug(f"Username '{user.username}' unchanged")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing user {user.username}: {str(e)}")
            # Still update sync timestamp to prevent constant retries
            user.last_synced_at = datetime.utcnow()
            db.commit()
            return False
    
    def get_users_to_sync(self, db: Session) -> List[User]:
        """Get users that need profile synchronization"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=settings.USERNAME_SYNC_MAX_AGE_HOURS)
        
        # Query users that need syncing
        users = db.query(User).filter(
            User.is_active == True,  # Only sync active users
            (User.last_synced_at.is_(None)) |  # Never synced
            (User.last_synced_at < cutoff_time)  # Not synced recently
        ).all()
        
        return users

# Global service instance
nostr_sync_service = NostrSyncService() 