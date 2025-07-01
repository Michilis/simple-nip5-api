import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.services.nip05 import npub_to_pubkey, validate_npub, normalize_username
from config import settings

logger = logging.getLogger(__name__)

class WhitelistService:
    def __init__(self):
        self.whitelist_file = os.getenv("WHITELIST_FILE", "whitelist.json")
        self.last_modified = None
        self.whitelist_data = None
    
    def _load_whitelist_file(self) -> Optional[Dict[str, Any]]:
        """Load and parse the whitelist.json file"""
        try:
            if not os.path.exists(self.whitelist_file):
                logger.info(f"Whitelist file {self.whitelist_file} not found - skipping whitelist sync")
                return None
            
            # Check if file has been modified
            file_stat = os.stat(self.whitelist_file)
            file_modified = file_stat.st_mtime
            
            if self.last_modified == file_modified and self.whitelist_data is not None:
                logger.debug("Whitelist file unchanged - using cached data")
                return self.whitelist_data
            
            # Read and parse the file
            with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if not isinstance(data, dict) or 'users' not in data:
                logger.error("Invalid whitelist.json format - missing 'users' array")
                return None
            
            if not isinstance(data['users'], list):
                logger.error("Invalid whitelist.json format - 'users' must be an array")
                return None
            
            self.last_modified = file_modified
            self.whitelist_data = data
            logger.info(f"Loaded whitelist file with {len(data['users'])} entries")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in whitelist file: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error loading whitelist file: {str(e)}")
            return None
    
    def _validate_and_normalize_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and normalize a whitelist entry"""
        try:
            # Required fields
            if not isinstance(entry, dict):
                logger.warning("Whitelist entry is not a dictionary")
                return None
            
            if 'pubkey' not in entry or 'username' not in entry:
                logger.warning("Whitelist entry missing required fields (pubkey, username)")
                return None
            
            pubkey_input = str(entry['pubkey']).strip()
            username_input = str(entry['username']).strip()
            
            # Convert pubkey to hex format
            if pubkey_input.startswith('npub1'):
                # Input is npub format
                if not validate_npub(pubkey_input):
                    logger.warning(f"Invalid npub format in whitelist: {pubkey_input}")
                    return None
                pubkey_hex = npub_to_pubkey(pubkey_input)
            elif len(pubkey_input) == 64:
                # Input is likely hex pubkey
                try:
                    # Validate it's a valid hex string
                    int(pubkey_input, 16)
                    pubkey_hex = pubkey_input.lower()
                except ValueError:
                    logger.warning(f"Invalid hex pubkey format in whitelist: {pubkey_input}")
                    return None
            else:
                logger.warning(f"Invalid pubkey format in whitelist: {pubkey_input}")
                return None
            
            # Validate and normalize username
            try:
                normalized_username = normalize_username(username_input)
            except ValueError as e:
                logger.warning(f"Invalid username '{username_input}' in whitelist: {str(e)}")
                return None
            
            # Get active status (default to true if not specified)
            active = entry.get('active', True)
            if not isinstance(active, bool):
                logger.warning(f"Invalid active value for {username_input} - must be boolean")
                active = True
            
            # Get optional note
            note = entry.get('note', '')
            if note and not isinstance(note, str):
                note = str(note)
            
            return {
                'pubkey': pubkey_hex,
                'username': normalized_username,
                'active': active,
                'note': note.strip() if note else ''
            }
            
        except Exception as e:
            logger.error(f"Error validating whitelist entry: {str(e)}")
            return None
    
    def sync_whitelist_to_database(self) -> Dict[str, int]:
        """Sync whitelist.json entries to the database"""
        stats = {
            'added': 0,
            'updated': 0,
            'deactivated': 0,
            'errors': 0
        }
        
        try:
            # Load whitelist file
            whitelist_data = self._load_whitelist_file()
            if not whitelist_data:
                return stats
            
            db = SessionLocal()
            try:
                # Process all whitelist entries
                whitelist_pubkeys = set()
                
                for entry in whitelist_data['users']:
                    normalized_entry = self._validate_and_normalize_entry(entry)
                    if not normalized_entry:
                        stats['errors'] += 1
                        continue
                    
                    pubkey = normalized_entry['pubkey']
                    username = normalized_entry['username']
                    active = normalized_entry['active']
                    note = normalized_entry['note']
                    
                    whitelist_pubkeys.add(pubkey)
                    
                    # Check if user exists in database
                    existing_user = db.query(User).filter(User.pubkey == pubkey).first()
                    
                    if existing_user:
                        # Update existing user
                        updated = False
                        
                        # Check if username needs updating
                        if existing_user.username != username:
                            # Check if new username is available
                            username_conflict = db.query(User).filter(
                                User.username == username,
                                User.pubkey != pubkey
                            ).first()
                            
                            if username_conflict:
                                # Whitelist.json takes precedence - rename conflicting user to temporary username
                                logger.warning(f"Username conflict: '{username}' taken by {username_conflict.pubkey[:8]}... - renaming to temporary username")
                                
                                # Generate temporary username for the conflicting user
                                temp_username = f"{username_conflict.pubkey[:8]}tmp"
                                counter = 1
                                original_temp = temp_username
                                while db.query(User).filter(User.username == temp_username).first():
                                    temp_username = f"{original_temp}{counter}"
                                    counter += 1
                                
                                # Update conflicting user to temporary username
                                old_conflicting_username = username_conflict.username
                                username_conflict.username = temp_username
                                username_conflict.username_manual = False  # Enable sync for renamed user
                                username_conflict.last_synced_at = None  # Queue for profile sync
                                
                                logger.info(f"Renamed conflicting user: '{old_conflicting_username}' -> '{temp_username}' (will sync from Nostr profile)")
                            
                            logger.info(f"Updating username: {existing_user.username} -> {username}")
                            existing_user.username = username
                            existing_user.username_manual = True  # Mark as manually set from whitelist
                            updated = True
                        
                        # Update active status
                        if existing_user.is_active != active:
                            logger.info(f"Updating active status for {username}: {existing_user.is_active} -> {active}")
                            existing_user.is_active = active
                            updated = True
                        
                        # Update note
                        current_note = existing_user.note or ""
                        if current_note != note:
                            existing_user.note = note if note else None
                            updated = True
                        
                        # Ensure whitelist users have lifetime subscription and manual username
                        if existing_user.subscription_type != "whitelist":
                            existing_user.subscription_type = "whitelist"
                            existing_user.expires_at = None
                            updated = True
                        
                        # Mark username as manually set from whitelist
                        if not existing_user.username_manual:
                            existing_user.username_manual = True
                            updated = True
                        
                        if updated:
                            stats['updated'] += 1
                    
                    else:
                        # Check if username is available
                        username_conflict = db.query(User).filter(User.username == username).first()
                        if username_conflict:
                            # Whitelist.json takes precedence - rename conflicting user to temporary username
                            logger.warning(f"Username conflict for new user '{username}': taken by {username_conflict.pubkey[:8]}... - renaming existing user")
                            
                            # Generate temporary username for the conflicting user
                            temp_username = f"{username_conflict.pubkey[:8]}tmp"
                            counter = 1
                            original_temp = temp_username
                            while db.query(User).filter(User.username == temp_username).first():
                                temp_username = f"{original_temp}{counter}"
                                counter += 1
                            
                            # Update conflicting user to temporary username
                            old_conflicting_username = username_conflict.username
                            username_conflict.username = temp_username
                            username_conflict.username_manual = False  # Enable sync for renamed user
                            username_conflict.last_synced_at = None  # Queue for profile sync
                            
                            logger.info(f"Renamed conflicting user: '{old_conflicting_username}' -> '{temp_username}' (will sync from Nostr profile)")
                        
                        # Create new user from whitelist
                        # Convert hex pubkey back to npub for storage
                        from app.services.nip05 import pubkey_to_npub
                        try:
                            npub = pubkey_to_npub(pubkey)
                        except Exception as e:
                            logger.error(f"Failed to convert pubkey to npub for {username}: {str(e)}")
                            stats['errors'] += 1
                            continue
                        
                        new_user = User(
                            username=username,
                            pubkey=pubkey,
                            npub=npub,
                            is_active=active,
                            subscription_type="whitelist",
                            expires_at=None,
                            note=note if note else None,
                            username_manual=True,  # Mark as manually set from whitelist
                            created_at=datetime.utcnow()
                        )
                        
                        db.add(new_user)
                        stats['added'] += 1
                        logger.info(f"Added new whitelist user: {username} ({'active' if active else 'inactive'})")
                
                # Handle users not in whitelist anymore
                # Find users with subscription_type="whitelist" not in current whitelist
                whitelist_users_in_db = db.query(User).filter(User.subscription_type == "whitelist").all()
                
                for db_user in whitelist_users_in_db:
                    if db_user.pubkey not in whitelist_pubkeys:
                        # User removed from whitelist - deactivate but don't delete
                        if db_user.is_active:
                            logger.info(f"Deactivating user removed from whitelist: {db_user.username}")
                            db_user.is_active = False
                            stats['deactivated'] += 1
                
                # Commit all changes
                db.commit()
                
                logger.info(f"Whitelist sync completed: {stats['added']} added, {stats['updated']} updated, {stats['deactivated']} deactivated, {stats['errors']} errors")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error during whitelist sync: {str(e)}")
                stats['errors'] += 1
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error during whitelist sync: {str(e)}")
            stats['errors'] += 1
        
        return stats
    
    def get_whitelist_status(self) -> Dict[str, Any]:
        """Get current whitelist file status"""
        try:
            if not os.path.exists(self.whitelist_file):
                return {
                    "exists": False,
                    "file_path": self.whitelist_file
                }
            
            file_stat = os.stat(self.whitelist_file)
            whitelist_data = self._load_whitelist_file()
            
            return {
                "exists": True,
                "file_path": self.whitelist_file,
                "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "file_size": file_stat.st_size,
                "entries_count": len(whitelist_data.get('users', [])) if whitelist_data else 0,
                "version": whitelist_data.get('metadata', {}).get('version', 'unknown') if whitelist_data else 'unknown'
            }
            
        except Exception as e:
            return {
                "exists": False,
                "error": str(e),
                "file_path": self.whitelist_file
            }

# Global service instance
whitelist_service = WhitelistService() 