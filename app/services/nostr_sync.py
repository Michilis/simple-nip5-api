import asyncio
import logging
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pynostr.relay_manager import RelayManager
from pynostr.filters import FiltersList, Filters
from pynostr.event import EventKind
from app.models import User
from app.database import get_db
from config import settings

logger = logging.getLogger(__name__)

async def fetch_nostr_profile(pubkey: str, timeout: int = 2) -> Optional[Dict[str, Any]]:
    """Fetch a user's Nostr profile (kind:0 event) from the configured relays using pynostr."""
    relay_manager = RelayManager(timeout=timeout)
    for relay in settings.NOSTR_RELAYS:
        relay_manager.add_relay(relay)
    filters = FiltersList([
        Filters(kinds=[EventKind.METADATA], authors=[pubkey], limit=1)
    ])
    subscription_id = uuid.uuid1().hex
    relay_manager.add_subscription_on_all_relays(subscription_id, filters)
    relay_manager.run_sync()
    await asyncio.sleep(timeout)
    profile = None
    while relay_manager.message_pool.has_events():
        event_msg = relay_manager.message_pool.get_event()
        if event_msg.event.kind == EventKind.METADATA:
            try:
                profile = json.loads(event_msg.event.content)
                break
            except Exception as e:
                logger.error(f"Error parsing profile JSON: {str(e)}")
    relay_manager.close_all_relay_connections()
    return profile

async def sync_username(users: List[User]):
    """Sync usernames from Nostr profiles using pynostr."""
    try:
        for user in users:
            if not user.pubkey:
                continue
            # Check if we need to sync (based on last_sync and max_age)
            if user.last_sync:
                age = datetime.utcnow() - user.last_sync
                if age < timedelta(hours=settings.USERNAME_SYNC_MAX_AGE_HOURS):
                    continue
            # Fetch profile from Nostr
            profile = await fetch_nostr_profile(user.pubkey)
            if profile:
                try:
                    # Update username if we got a valid name
                    if 'name' in profile and profile['name']:
                        user.username = profile['name']
                        user.last_sync = datetime.utcnow()
                        db = next(get_db())
                        db.commit()
                        logger.info(f"Updated username for {user.pubkey} to {user.username}")
                except Exception as e:
                    logger.error(f"Error updating username for {user.pubkey}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in sync_username: {str(e)}")

async def run_sync_loop():
    """Run the username sync loop using pynostr."""
    while True:
        try:
            if not settings.USERNAME_SYNC_ENABLED:
                await asyncio.sleep(60)
                continue
            # Get all active users
            db = next(get_db())
            users = db.query(User).filter(User.is_active == True).all()
            # Sync usernames
            await sync_username(users)
            # Wait for next sync interval
            await asyncio.sleep(settings.USERNAME_SYNC_INTERVAL_MINUTES * 60)
        except Exception as e:
            logger.error(f"Error in sync loop: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

# Export the functions directly
__all__ = ['fetch_nostr_profile', 'sync_username', 'run_sync_loop'] 