import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models import Invoice, User
from app.services.lnbits import lnbits_service
from app.services.nostr_sync import nostr_sync_service
from config import settings

logger = logging.getLogger(__name__)

class InvoiceScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    def start(self):
        """Start the background scheduler"""
        if not self.is_running:
            # Invoice polling job (only if LNbits is enabled)
            if settings.LNBITS_ENABLED:
                self.scheduler.add_job(
                    self.poll_unpaid_invoices,
                    IntervalTrigger(seconds=60),  # Check every minute
                    id='poll_invoices',
                    replace_existing=True
                )
                logger.info("Invoice polling enabled")
            else:
                logger.info("Invoice polling disabled (LNbits disabled)")
            
            # Username sync job (if enabled)
            if settings.USERNAME_SYNC_ENABLED:
                self.scheduler.add_job(
                    self.sync_usernames,
                    IntervalTrigger(minutes=settings.USERNAME_SYNC_INTERVAL_MINUTES),
                    id='sync_usernames',
                    replace_existing=True
                )
                logger.info(f"Username sync enabled - running every {settings.USERNAME_SYNC_INTERVAL_MINUTES} minutes")
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Background scheduler started")
    
    def stop(self):
        """Stop the background scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Background scheduler stopped")
    
    async def poll_unpaid_invoices(self):
        """Poll all unpaid invoices that are due for checking"""
        if not settings.LNBITS_ENABLED:
            logger.debug("Invoice polling skipped (LNbits disabled)")
            return
            
        db = SessionLocal()
        try:
            current_time = datetime.utcnow()
            
            # Get unpaid invoices that need polling
            invoices_to_poll = db.query(Invoice).filter(
                Invoice.status == "unpaid",
                Invoice.expires_at > current_time,  # Not expired
                Invoice.next_poll_time <= current_time  # Due for polling
            ).all()
            
            logger.info(f"Polling {len(invoices_to_poll)} unpaid invoices")
            
            for invoice in invoices_to_poll:
                await self.check_invoice_payment(db, invoice)
                
        except Exception as e:
            logger.error(f"Error polling invoices: {str(e)}")
        finally:
            db.close()
    
    async def sync_usernames(self):
        """Sync usernames from Nostr profiles"""
        if not settings.USERNAME_SYNC_ENABLED:
            return
            
        db = SessionLocal()
        try:
            # Get users that need syncing
            users_to_sync = nostr_sync_service.get_users_to_sync(db)
            
            if not users_to_sync:
                logger.debug("No users need username sync")
                return
            
            logger.info(f"Syncing usernames for {len(users_to_sync)} users")
            
            updates_count = 0
            for user in users_to_sync:
                try:
                    # Rate limiting: small delay between users
                    if users_to_sync.index(user) > 0:
                        await asyncio.sleep(1)
                    
                    updated = await nostr_sync_service.sync_user_profile(user, db)
                    if updated:
                        updates_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to sync user {user.username}: {str(e)}")
                    continue
            
            if updates_count > 0:
                logger.info(f"Username sync completed: {updates_count} usernames updated")
            else:
                logger.debug("Username sync completed: no updates needed")
                
        except Exception as e:
            logger.error(f"Error during username sync: {str(e)}")
        finally:
            db.close()
    
    async def check_invoice_payment(self, db: Session, invoice: Invoice):
        """Check a single invoice for payment"""
        if not settings.LNBITS_ENABLED:
            return
            
        try:
            # Check payment status via LNbits
            is_paid = await lnbits_service.verify_payment(invoice.payment_hash)
            
            if is_paid:
                # Payment confirmed - activate user
                await self.activate_user(db, invoice)
                logger.info(f"Payment confirmed for invoice {invoice.payment_hash}")
            else:
                # Update polling schedule
                self.update_polling_schedule(db, invoice)
                
        except Exception as e:
            logger.error(f"Error checking invoice {invoice.payment_hash}: {str(e)}")
            # Update polling schedule even on error
            self.update_polling_schedule(db, invoice)
    
    async def activate_user(self, db: Session, invoice: Invoice):
        """Activate user after successful payment"""
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == invoice.username).first()
            
            if existing_user:
                # Update existing user
                existing_user.pubkey = invoice.pubkey
                existing_user.npub = invoice.npub
                existing_user.is_active = True
            else:
                # Create new user
                new_user = User(
                    username=invoice.username,
                    pubkey=invoice.pubkey,
                    npub=invoice.npub,
                    is_active=True
                )
                db.add(new_user)
            
            # Update invoice status
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"User {invoice.username} activated successfully")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error activating user {invoice.username}: {str(e)}")
            raise
    
    def update_polling_schedule(self, db: Session, invoice: Invoice):
        """Update the next polling time based on current attempts"""
        if not settings.LNBITS_ENABLED:
            return
            
        try:
            invoice.poll_attempts += 1
            current_time = datetime.utcnow()
            
            # Calculate time since invoice creation
            time_since_creation = (current_time - invoice.created_at).total_seconds()
            
            if time_since_creation > settings.POLL_MAX_TIME:
                # Stop polling after max time
                invoice.next_poll_time = None
                logger.info(f"Stopped polling expired invoice {invoice.payment_hash}")
            elif time_since_creation < settings.POLL_SWITCH_TIME:
                # Poll every minute for first 10 minutes
                invoice.next_poll_time = current_time + timedelta(seconds=settings.POLL_INITIAL_INTERVAL)
            else:
                # Poll every 5 minutes after 10 minutes
                invoice.next_poll_time = current_time + timedelta(seconds=settings.POLL_LATER_INTERVAL)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating polling schedule for invoice {invoice.payment_hash}: {str(e)}")
    
    async def schedule_invoice_polling(self, payment_hash: str):
        """Schedule a new invoice for polling"""
        if not settings.LNBITS_ENABLED:
            logger.debug("Invoice polling scheduling skipped (LNbits disabled)")
            return
            
        db = SessionLocal()
        try:
            invoice = db.query(Invoice).filter(Invoice.payment_hash == payment_hash).first()
            if invoice:
                # Set initial polling time
                invoice.next_poll_time = datetime.utcnow() + timedelta(seconds=settings.POLL_INITIAL_INTERVAL)
                db.commit()
                logger.info(f"Scheduled polling for invoice {payment_hash}")
        except Exception as e:
            logger.error(f"Error scheduling invoice polling: {str(e)}")
        finally:
            db.close()

# Global scheduler instance
invoice_scheduler = InvoiceScheduler() 