"""
Background task scheduler for FastAPI template.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """Background task scheduler for periodic operations."""
    
    def __init__(self):
        """Initialize the scheduler."""
        self.tasks: Dict[str, Any] = {}
        self.is_running = False
    
    async def start(self):
        """Start the background scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        logger.info("Starting background scheduler")
        
        # Start background tasks
        asyncio.create_task(self._run_periodic_tasks())
    
    async def stop(self):
        """Stop the background scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.is_running = False
        logger.info("Stopping background scheduler")
        
        # Cancel all running tasks
        for task_name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled task: {task_name}")
    
    async def _run_periodic_tasks(self):
        """Run periodic background tasks."""
        while self.is_running:
            try:
                logger.debug("Running periodic tasks")
                
                # Add your periodic tasks here
                await self._cleanup_old_data()
                await self._health_check()
                
                # Wait for next cycle (e.g., every hour)
                await asyncio.sleep(3600)  # 1 hour
                
            except asyncio.CancelledError:
                logger.info("Periodic tasks cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic tasks: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _cleanup_old_data(self):
        """Clean up old data (placeholder for customization)."""
        try:
            logger.debug("Running data cleanup task")
            # Add your cleanup logic here
            # For example: delete old items, clean up temporary files, etc.
            pass
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
    
    async def _health_check(self):
        """Perform health checks (placeholder for customization)."""
        try:
            logger.debug("Running health check task")
            # Add your health check logic here
            # For example: check external services, verify data integrity, etc.
            pass
        except Exception as e:
            logger.error(f"Error in health check task: {e}")
    
    async def run_tasks(self) -> Dict[str, Any]:
        """Manually trigger all background tasks."""
        try:
            logger.info("Manually running background tasks")
            
            tasks_run = 0
            
            # Run cleanup task
            await self._cleanup_old_data()
            tasks_run += 1
            
            # Run health check task
            await self._health_check()
            tasks_run += 1
            
            logger.info(f"Completed {tasks_run} background tasks")
            return {"tasks_run": tasks_run}
            
        except Exception as e:
            logger.error(f"Error running manual tasks: {e}")
            raise RuntimeError(f"Failed to run background tasks: {e}")
    
    def add_task(self, name: str, task_func, *args, **kwargs):
        """Add a custom task to the scheduler."""
        if name in self.tasks:
            logger.warning(f"Task {name} already exists, replacing")
        
        self.tasks[name] = asyncio.create_task(task_func(*args, **kwargs))
        logger.info(f"Added task: {name}")
    
    def remove_task(self, name: str):
        """Remove a task from the scheduler."""
        if name in self.tasks:
            task = self.tasks[name]
            if not task.done():
                task.cancel()
            del self.tasks[name]
            logger.info(f"Removed task: {name}")
        else:
            logger.warning(f"Task {name} not found")


# Global scheduler instance
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def set_scheduler(scheduler: BackgroundScheduler):
    """Set the global scheduler instance."""
    global _scheduler
    _scheduler = scheduler 