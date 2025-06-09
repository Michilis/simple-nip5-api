import re
import binascii
from typing import Dict, Optional
from bech32 import bech32_decode, bech32_encode, convertbits

def normalize_username(username: str) -> str:
    """Normalize username according to NIP-05 specs"""
    # Convert to lowercase and remove invalid characters
    normalized = re.sub(r'[^a-z0-9._-]', '', username.lower().strip())
    
    # Must start with alphanumeric
    if not normalized or not normalized[0].isalnum():
        raise ValueError("Username must start with alphanumeric character")
    
    # Check length
    if len(normalized) < 1 or len(normalized) > 50:
        raise ValueError("Username must be between 1 and 50 characters")
    
    return normalized

def npub_to_pubkey(npub: str) -> str:
    """Convert npub (bech32) to hex pubkey"""
    if not npub.startswith('npub1'):
        raise ValueError("Invalid npub format")
    
    try:
        hrp, data = bech32_decode(npub)
        if hrp != 'npub' or data is None:
            raise ValueError("Invalid npub format")
        
        # Convert from 5-bit to 8-bit
        decoded = convertbits(data, 5, 8, False)
        if decoded is None or len(decoded) != 32:
            raise ValueError("Invalid npub data")
        
        # Convert to hex
        pubkey_hex = bytes(decoded).hex()
        return pubkey_hex
    except Exception as e:
        raise ValueError(f"Failed to decode npub: {str(e)}")

def pubkey_to_npub(pubkey_hex: str) -> str:
    """Convert hex pubkey to npub (bech32)"""
    try:
        # Validate hex
        if len(pubkey_hex) != 64:
            raise ValueError("Pubkey must be 64 hex characters")
        
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        
        # Convert to 5-bit
        data = convertbits(pubkey_bytes, 8, 5)
        if data is None:
            raise ValueError("Failed to convert pubkey")
        
        # Encode as bech32
        npub = bech32_encode('npub', data)
        if npub is None:
            raise ValueError("Failed to encode npub")
        
        return npub
    except Exception as e:
        raise ValueError(f"Failed to encode npub: {str(e)}")

def validate_npub(npub: str) -> bool:
    """Validate npub format and checksum"""
    try:
        npub_to_pubkey(npub)
        return True
    except:
        return False

def is_username_available(username: str, existing_users: list) -> bool:
    """Check if username is available"""
    normalized = normalize_username(username)
    return normalized not in [user.lower() for user in existing_users]

def generate_nostr_json(active_users: Dict[str, str]) -> Dict:
    """Generate .well-known/nostr.json response"""
    return {
        "names": active_users
    } 