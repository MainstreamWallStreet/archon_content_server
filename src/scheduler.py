"""Background task scheduler for Banshee API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.banshee_watchlist import BansheeStore
from src.earnings_alerts import (
    GcsBucket,
    refresh_upcoming_calls,
    cleanup_past_data,
    send_due_emails,
)

logger = logging.getLogger(__name__)


class BansheeScheduler:
    """Background scheduler for Banshee operations."""
    
    def __init__(
        self,
        store: BansheeStore,
        calls_bucket: GcsBucket,
        email_bucket: GcsBucket,
    ):
        self.store = store
        self.calls_bucket = calls_bucket
        self.email_bucket = email_bucket
        self._running = False
        self._tasks: list[asyncio.Task] = []
        
    async def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
            
        logger.info("Starting Banshee background scheduler")
        self._running = True
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._daily_sync_loop()),
            asyncio.create_task(self._email_dispatch_loop()),
        ]
        
        logger.info("Background scheduler started with %d tasks", len(self._tasks))
        
    async def stop(self):
        """Stop the background scheduler."""
        if not self._running:
            logger.warning("Scheduler is not running")
            return
            
        logger.info("Stopping Banshee background scheduler")
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        self._tasks.clear()
        logger.info("Background scheduler stopped")
        
    async def _daily_sync_loop(self):
        """Run daily sync operations at 19:00 EST (00:00 UTC)."""
        logger.info("Starting daily sync loop")
        
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                
                # Check if it's time for daily sync (00:00 UTC = 19:00 EST previous day)
                if now.hour == 0 and now.minute < 5:  # Run within first 5 minutes of hour
                    logger.info("Executing daily sync at %s", now.isoformat())
                    
                    try:
                        # Refresh upcoming calls
                        await refresh_upcoming_calls(
                            self.store, 
                            self.calls_bucket, 
                            self.email_bucket
                        )
                        
                        # Clean up past data
                        cleanup_past_data(self.calls_bucket, self.email_bucket)
                        
                        logger.info("Daily sync completed successfully")
                        
                        # Wait until next day to avoid multiple runs
                        await asyncio.sleep(3600)  # Wait 1 hour
                        
                    except Exception as e:
                        logger.error("Error during daily sync: %s", str(e))
                        await asyncio.sleep(300)  # Wait 5 minutes before retry
                        
                else:
                    # Check every 5 minutes
                    await asyncio.sleep(300)
                    
            except asyncio.CancelledError:
                logger.info("Daily sync loop cancelled")
                break
            except Exception as e:
                logger.error("Unexpected error in daily sync loop: %s", str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retry
                
    async def _email_dispatch_loop(self):
        """Run email dispatch every hour."""
        logger.info("Starting email dispatch loop")
        
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                logger.info("Checking for due emails at %s", now.isoformat())
                
                try:
                    # Send due emails
                    send_due_emails(self.email_bucket)
                    logger.info("Email dispatch check completed")
                    
                except Exception as e:
                    logger.error("Error during email dispatch: %s", str(e))
                    
                # Wait 1 hour before next check
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Email dispatch loop cancelled")
                break
            except Exception as e:
                logger.error("Unexpected error in email dispatch loop: %s", str(e))
                await asyncio.sleep(300)  # Wait 5 minutes before retry
                
    async def trigger_daily_sync(self):
        """Manually trigger daily sync operations."""
        logger.info("Manually triggering daily sync")
        try:
            await refresh_upcoming_calls(
                self.store, 
                self.calls_bucket, 
                self.email_bucket
            )
            cleanup_past_data(self.calls_bucket, self.email_bucket)
            logger.info("Manual daily sync completed successfully")
        except Exception as e:
            logger.error("Error during manual daily sync: %s", str(e))
            raise
            
    async def trigger_email_dispatch(self):
        """Manually trigger email dispatch."""
        logger.info("Manually triggering email dispatch")
        try:
            send_due_emails(self.email_bucket)
            logger.info("Manual email dispatch completed successfully")
        except Exception as e:
            logger.error("Error during manual email dispatch: %s", str(e))
            raise


# Global scheduler instance
_scheduler: Optional[BansheeScheduler] = None


def get_scheduler() -> Optional[BansheeScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


def set_scheduler(scheduler: BansheeScheduler):
    """Set the global scheduler instance."""
    global _scheduler
    _scheduler = scheduler 