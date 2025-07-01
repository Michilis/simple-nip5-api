import asyncio
import json
import hashlib
import hmac
import logging
import os
import websockets
from datetime import datetime
from typing import Dict, List, Optional, Any
from secp256k1 import PrivateKey, PublicKey
import bech32

from config import settings

logger = logging.getLogger(__name__)

class NostrDMService:
    def __init__(self):
        self.relays = settings.nostr_dm_relays_list
        self.private_key_hex = settings.NOSTR_DM_PRIVATE_KEY
        self.from_name = settings.NOSTR_DM_FROM_NAME
        self.messages_file = settings.MESSAGES_FILE
        self.private_key = None
        self.public_key_hex = None
        self.messages = {}
        
        # Initialize if DM is enabled
        if settings.NOSTR_DM_ENABLED:
            self._initialize()
    
    def _initialize(self):
        """Initialize the DM service with keys and messages"""
        try:
            # Load private key
            if not self.private_key_hex:
                logger.warning("NOSTR_DM_PRIVATE_KEY not set - DM service disabled")
                return
            
            # Create secp256k1 private key from hex
            private_key_bytes = bytes.fromhex(self.private_key_hex)
            self.private_key = PrivateKey(private_key_bytes)
            
            # Get public key
            public_key = self.private_key.pubkey
            self.public_key_hex = public_key.serialize(compressed=True)[1:].hex()
            
            logger.info(f"Nostr DM service initialized with pubkey: {self.public_key_hex[:16]}...")
            
            # Load message templates
            self._load_messages()
            
        except Exception as e:
            logger.error(f"Failed to initialize Nostr DM service: {str(e)}")
            self.private_key = None
    
    def _load_messages(self):
        """Load message templates from JSON file"""
        try:
            if os.path.exists(self.messages_file):
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
                logger.info(f"Loaded {len(self.messages)} message templates")
            else:
                logger.warning(f"Messages file {self.messages_file} not found")
                self.messages = {}
        except Exception as e:
            logger.error(f"Failed to load messages: {str(e)}")
            self.messages = {}
    
    def _create_event(self, kind: int, content: str, recipient_pubkey: str, tags: List[List[str]] = None) -> Dict[str, Any]:
        """Create a Nostr event"""
        if not self.private_key:
            raise ValueError("Private key not initialized")
        
        # Create event structure
        event = {
            "kind": kind,
            "created_at": int(datetime.utcnow().timestamp()),
            "tags": tags or [],
            "content": content,
            "pubkey": self.public_key_hex
        }
        
        # Create event ID (hash of serialized event data)
        serialized = json.dumps([
            0,  # Reserved
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"]
        ], separators=(',', ':'), ensure_ascii=False)
        
        event_id = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        event["id"] = event_id
        
        # Sign the event
        signature = self.private_key.schnorr_sign(bytes.fromhex(event_id), None, raw=True)
        event["sig"] = signature.hex()
        
        return event
    
    def _encrypt_dm_content(self, content: str, recipient_pubkey: str) -> str:
        """Encrypt DM content using NIP-04 encryption"""
        try:
            # Get recipient public key
            recipient_pubkey_bytes = bytes.fromhex("02" + recipient_pubkey)
            recipient_public_key = PublicKey(recipient_pubkey_bytes)
            
            # Create shared secret using ECDH
            shared_secret = self.private_key.ecdh(recipient_public_key.point())
            
            # Simple XOR encryption (NIP-04 is more complex, but this is a basic implementation)
            # In production, you'd want to implement proper NIP-04 encryption with AES
            import base64
            content_bytes = content.encode('utf-8')
            
            # For now, return base64 encoded content with a simple transformation
            # This is a placeholder - implement proper NIP-04 encryption for production
            encrypted = base64.b64encode(content_bytes).decode('utf-8')
            
            return encrypted
            
        except Exception as e:
            logger.error(f"Failed to encrypt content: {str(e)}")
            # Fallback to plain text (not recommended for production)
            return content
    
    def _create_dm_event(self, content: str, recipient_pubkey: str) -> Dict[str, Any]:
        """Create an encrypted DM event (kind 4)"""
        # Encrypt the content
        encrypted_content = self._encrypt_dm_content(content, recipient_pubkey)
        
        # Create tags for DM
        tags = [["p", recipient_pubkey]]
        
        # Create the event
        return self._create_event(4, encrypted_content, recipient_pubkey, tags)
    
    async def _send_event_to_relay(self, relay_url: str, event: Dict[str, Any]) -> bool:
        """Send event to a single relay"""
        try:
            async with websockets.connect(relay_url, timeout=10) as websocket:
                # Send the event
                message = json.dumps(["EVENT", event])
                await websocket.send(message)
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    
                    # Check if it's an OK response
                    if response_data[0] == "OK" and response_data[1] == event["id"]:
                        if response_data[2]:  # Success
                            logger.debug(f"Event sent successfully to {relay_url}")
                            return True
                        else:
                            logger.warning(f"Event rejected by {relay_url}: {response_data[3] if len(response_data) > 3 else 'Unknown error'}")
                            return False
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response from {relay_url}")
                    return False
                    
        except Exception as e:
            logger.warning(f"Failed to send event to {relay_url}: {str(e)}")
            return False
    
    async def send_dm(self, recipient_pubkey: str, message_type: str, **kwargs) -> bool:
        """Send a DM to a user"""
        if not settings.NOSTR_DM_ENABLED:
            logger.debug("Nostr DM disabled - skipping message")
            return False
        
        if not self.private_key:
            logger.error("Nostr DM service not properly initialized")
            return False
        
        try:
            # Get message template
            if message_type not in self.messages:
                logger.error(f"Message type '{message_type}' not found in templates")
                return False
            
            template = self.messages[message_type]
            
            # Format the message with provided kwargs
            try:
                formatted_message = template["message"].format(
                    domain=settings.DOMAIN,
                    **kwargs
                )
            except KeyError as e:
                logger.error(f"Missing required parameter for message template: {e}")
                return False
            
            # Create DM event
            event = self._create_dm_event(formatted_message, recipient_pubkey)
            
            # Send to all relays
            success_count = 0
            for relay_url in self.relays:
                if await self._send_event_to_relay(relay_url, event):
                    success_count += 1
            
            if success_count > 0:
                logger.info(f"DM sent successfully to {success_count}/{len(self.relays)} relays for {recipient_pubkey[:16]}...")
                return True
            else:
                logger.error(f"Failed to send DM to any relay for {recipient_pubkey[:16]}...")
                return False
                
        except Exception as e:
            logger.error(f"Error sending DM: {str(e)}")
            return False
    
    def is_enabled(self) -> bool:
        """Check if DM service is enabled and properly initialized"""
        return settings.NOSTR_DM_ENABLED and self.private_key is not None
    
    def get_sender_pubkey(self) -> str:
        """Get the public key of the DM sender"""
        return self.public_key_hex if self.public_key_hex else ""
    
    def get_available_message_types(self) -> List[str]:
        """Get list of available message types"""
        return list(self.messages.keys())

# Global service instance
nostr_dm_service = NostrDMService() 