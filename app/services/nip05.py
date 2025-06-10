import re
import binascii
from typing import Dict, Optional
import bech32

def normalize_username(username: str) -> str:
    """Normalize username to lowercase and remove invalid characters"""
    if not username:
        raise ValueError("Username cannot be empty")
    
    # Convert to lowercase
    username = username.lower()
    
    # Remove any characters that aren't alphanumeric, dots, dashes, or underscores
    username = re.sub(r'[^a-z0-9._-]', '', username)
    
    # Ensure username starts with alphanumeric
    if not re.match(r'^[a-z0-9]', username):
        raise ValueError("Username must start with an alphanumeric character")
    
    # Ensure username is between 1 and 50 characters
    if len(username) < 1 or len(username) > 50:
        raise ValueError("Username must be between 1 and 50 characters")
    
    return username

def validate_npub(npub: str) -> bool:
    """Validate npub format"""
    if not npub:
        return False
    
    # If it's a hex pubkey, it's valid
    if is_hex_pubkey(npub):
        return True
    
    # Must start with npub1
    if not npub.startswith('npub1'):
        return False
    
    try:
        # Try to decode
        _, data = bech32.bech32_decode(npub)
        return data is not None
    except:
        return False

def is_hex_pubkey(pubkey: str) -> bool:
    """Check if string is a valid hex pubkey"""
    if not pubkey:
        return False
    
    # Must be 64 characters of hex
    if len(pubkey) != 64:
        return False
    
    try:
        int(pubkey, 16)
        return True
    except ValueError:
        return False

def npub_to_pubkey(npub: str) -> str:
    """Convert npub (bech32) to hex pubkey"""
    if not npub:
        raise ValueError("Npub cannot be empty")
    
    # If it's already a hex pubkey, return it
    if is_hex_pubkey(npub):
        return npub
    
    # Must start with npub1
    if not npub.startswith('npub1'):
        raise ValueError("Invalid npub format")
    
    try:
        # Decode bech32
        _, data = bech32.bech32_decode(npub)
        if not data:
            raise ValueError("Invalid bech32 encoding")
        
        # Convert to hex
        pubkey = ''.join([f'{x:02x}' for x in data])
        return pubkey
    except Exception as e:
        raise ValueError(f"Failed to decode npub: {str(e)}")

def pubkey_to_npub(pubkey: str) -> str:
    """Convert hex pubkey to npub"""
    if not is_hex_pubkey(pubkey):
        raise ValueError("Invalid pubkey format")
    
    # Add 'npub' prefix
    return f"npub{pubkey}"

def is_username_available(username: str, existing_users: list) -> bool:
    """Check if username is available"""
    normalized = normalize_username(username)
    return normalized not in [user.lower() for user in existing_users]

def generate_nostr_json(active_users: Dict[str, str]) -> Dict:
    """Generate .well-known/nostr.json response"""
    return {
        "names": active_users
    } 