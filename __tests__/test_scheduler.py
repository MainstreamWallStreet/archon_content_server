"""Tests for the BansheeScheduler background task scheduler."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.scheduler import BansheeScheduler, get_scheduler, set_scheduler


@pytest.fixture
def mock_store():
    """Mock BansheeStore."""
    store = MagicMock()
    store.list_tickers.return_value = ["AAPL", "MSFT"]
    return store


@pytest.fixture
def mock_calls_bucket():
    """Mock calls bucket."""
    bucket = MagicMock()
    bucket.name = "test-calls-bucket"
    return bucket


@pytest.fixture
def mock_email_bucket():
    """Mock email bucket."""
    bucket = MagicMock()
    bucket.name = "test-email-bucket"
    return bucket


@pytest.fixture
def scheduler(mock_store, mock_calls_bucket, mock_email_bucket):
    """Create a BansheeScheduler instance for testing."""
    return BansheeScheduler(mock_store, mock_calls_bucket, mock_email_bucket)


class TestBansheeScheduler:
    """Test the BansheeScheduler class."""

    def test_scheduler_initialization(self, scheduler):
        """Test scheduler is properly initialized."""
        assert scheduler.store is not None
        assert scheduler.calls_bucket is not None
        assert scheduler.email_bucket is not None
        assert scheduler._running is False
        assert scheduler._tasks == []

    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler):
        """Test starting the scheduler."""
        assert scheduler._running is False
        
        await scheduler.start()
        
        assert scheduler._running is True
        assert len(scheduler._tasks) == 2  # daily_sync and email_dispatch tasks

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler):
        """Test stopping the scheduler."""
        await scheduler.start()
        assert scheduler._running is True
        
        await scheduler.stop()
        
        assert scheduler._running is False
        assert scheduler._tasks == []

    @pytest.mark.asyncio
    async def test_start_already_running_scheduler(self, scheduler):
        """Test starting an already running scheduler."""
        await scheduler.start()
        assert scheduler._running is True
        
        # Should not start again
        await scheduler.start()
        assert scheduler._running is True
        assert len(scheduler._tasks) == 2

    @pytest.mark.asyncio
    async def test_stop_not_running_scheduler(self, scheduler):
        """Test stopping a scheduler that's not running."""
        assert scheduler._running is False
        
        # Should not error
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_trigger_daily_sync(self, scheduler):
        """Test manually triggering daily sync."""
        with patch("src.scheduler.refresh_upcoming_calls") as mock_refresh, \
             patch("src.scheduler.cleanup_past_data") as mock_cleanup:
            
            await scheduler.trigger_daily_sync()
            
            mock_refresh.assert_called_once_with(
                scheduler.store,
                scheduler.calls_bucket,
                scheduler.email_bucket
            )
            mock_cleanup.assert_called_once_with(
                scheduler.calls_bucket,
                scheduler.email_bucket
            )

    @pytest.mark.asyncio
    async def test_trigger_daily_sync_error_handling(self, scheduler):
        """Test error handling in daily sync."""
        with patch("src.scheduler.refresh_upcoming_calls", side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                await scheduler.trigger_daily_sync()

    @pytest.mark.asyncio
    async def test_trigger_email_dispatch(self, scheduler):
        """Test manually triggering email dispatch."""
        with patch("src.scheduler.send_due_emails") as mock_send:
            await scheduler.trigger_email_dispatch()
            
            mock_send.assert_called_once_with(scheduler.email_bucket)

    @pytest.mark.asyncio
    async def test_trigger_email_dispatch_error_handling(self, scheduler):
        """Test error handling in email dispatch."""
        with patch("src.scheduler.send_due_emails", side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                await scheduler.trigger_email_dispatch()

    @pytest.mark.asyncio
    async def test_daily_sync_loop_runs_at_midnight(self, scheduler):
        """Test that daily sync runs at midnight UTC."""
        with patch("src.scheduler.refresh_upcoming_calls") as mock_refresh, \
             patch("src.scheduler.cleanup_past_data") as mock_cleanup, \
             patch("src.scheduler.datetime") as mock_datetime:
            
            # Mock current time to be midnight UTC
            mock_now = datetime(2025, 1, 1, 0, 2, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            
            # Start the scheduler
            await scheduler.start()
            
            # Wait a bit for the loop to run
            await asyncio.sleep(0.1)
            
            # Stop the scheduler
            await scheduler.stop()
            
            # Verify daily sync was called
            mock_refresh.assert_called_once()
            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_sync_loop_skips_non_midnight(self, scheduler):
        """Test that daily sync doesn't run at non-midnight times."""
        with patch("src.scheduler.refresh_upcoming_calls") as mock_refresh, \
             patch("src.scheduler.datetime") as mock_datetime:
            
            # Mock current time to be 2 PM UTC (not midnight)
            mock_now = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            
            # Start the scheduler
            await scheduler.start()
            
            # Wait a bit for the loop to run
            await asyncio.sleep(0.1)
            
            # Stop the scheduler
            await scheduler.stop()
            
            # Verify daily sync was NOT called
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_dispatch_loop_runs_hourly(self, scheduler):
        """Test that email dispatch runs every hour."""
        with patch("src.scheduler.send_due_emails") as mock_send:
            # Start the scheduler
            await scheduler.start()
            
            # Wait a bit for the loop to run
            await asyncio.sleep(0.1)
            
            # Stop the scheduler
            await scheduler.stop()
            
            # Verify email dispatch was called
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_handles_cancellation(self, scheduler):
        """Test that scheduler handles task cancellation gracefully."""
        await scheduler.start()
        assert len(scheduler._tasks) == 2
        
        # Cancel the scheduler
        await scheduler.stop()
        
        # Verify tasks are cleaned up
        assert scheduler._tasks == []
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_scheduler_error_recovery(self, scheduler):
        """Test that scheduler recovers from errors in background tasks."""
        with patch("src.scheduler.refresh_upcoming_calls", side_effect=Exception("Test error")), \
             patch("src.scheduler.send_due_emails", side_effect=Exception("Test error")):
            
            # Start the scheduler
            await scheduler.start()
            
            # Wait a bit for the loop to run and encounter errors
            await asyncio.sleep(0.1)
            
            # Stop the scheduler
            await scheduler.stop()
            
            # Verify scheduler is still in a clean state
            assert scheduler._running is False
            assert scheduler._tasks == []


class TestGlobalScheduler:
    """Test global scheduler functions."""

    def test_get_scheduler_initial_state(self):
        """Test get_scheduler returns None initially."""
        # Reset the global scheduler for this test
        from src.scheduler import _scheduler
        import src.scheduler
        original_scheduler = src.scheduler._scheduler
        src.scheduler._scheduler = None
        
        try:
            assert get_scheduler() is None
        finally:
            # Restore the original scheduler
            src.scheduler._scheduler = original_scheduler

    def test_set_and_get_scheduler(self, scheduler):
        """Test setting and getting the global scheduler."""
        set_scheduler(scheduler)
        assert get_scheduler() is scheduler

    def test_set_scheduler_overwrites_previous(self, mock_store, mock_calls_bucket, mock_email_bucket):
        """Test that set_scheduler overwrites the previous scheduler."""
        scheduler1 = BansheeScheduler(mock_store, mock_calls_bucket, mock_email_bucket)
        scheduler2 = BansheeScheduler(mock_store, mock_calls_bucket, mock_email_bucket)
        
        set_scheduler(scheduler1)
        assert get_scheduler() is scheduler1
        
        set_scheduler(scheduler2)
        assert get_scheduler() is scheduler2


class TestSchedulerIntegration:
    """Integration tests for the scheduler."""

    @pytest.mark.asyncio
    async def test_scheduler_with_real_operations(self, mock_store, mock_calls_bucket, mock_email_bucket):
        """Test scheduler with mocked but realistic operations."""
        scheduler = BansheeScheduler(mock_store, mock_calls_bucket, mock_email_bucket)
        
        # Mock the operations to return success
        with patch("src.scheduler.refresh_upcoming_calls") as mock_refresh, \
             patch("src.scheduler.cleanup_past_data") as mock_cleanup, \
             patch("src.scheduler.send_due_emails") as mock_send:
            
            # Test manual triggers
            await scheduler.trigger_daily_sync()
            await scheduler.trigger_email_dispatch()
            
            # Verify operations were called
            mock_refresh.assert_called_once()
            mock_cleanup.assert_called_once()
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_persistence_across_restarts(self, mock_store, mock_calls_bucket, mock_email_bucket):
        """Test that scheduler state persists correctly across start/stop cycles."""
        scheduler = BansheeScheduler(mock_store, mock_calls_bucket, mock_email_bucket)
        
        # Start and stop multiple times
        for _ in range(3):
            await scheduler.start()
            assert scheduler._running is True
            assert len(scheduler._tasks) == 2
            
            await scheduler.stop()
            assert scheduler._running is False
            assert scheduler._tasks == []


class TestSchedulerTiming:
    """Test scheduler timing behavior."""

    @pytest.mark.asyncio
    async def test_daily_sync_timing_window(self, scheduler):
        """Test that daily sync only runs in the correct time window."""
        with patch("src.scheduler.refresh_upcoming_calls") as mock_refresh, \
             patch("src.scheduler.datetime") as mock_datetime:
            
            # Test different times
            test_times = [
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),  # Midnight - should run
                datetime(2025, 1, 1, 0, 4, 0, tzinfo=timezone.utc),  # 4 minutes past - should run
                datetime(2025, 1, 1, 0, 6, 0, tzinfo=timezone.utc),  # 6 minutes past - should NOT run
                datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), # Noon - should NOT run
            ]
            
            for test_time in test_times:
                mock_datetime.now.return_value = test_time
                
                # Reset mock
                mock_refresh.reset_mock()
                
                # Start scheduler briefly
                await scheduler.start()
                await asyncio.sleep(0.1)
                await scheduler.stop()
                
                # Check if refresh was called based on time
                if test_time.hour == 0 and test_time.minute < 5:
                    mock_refresh.assert_called_once()
                else:
                    mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_dispatch_frequency(self, scheduler):
        """Test that email dispatch runs at the expected frequency."""
        with patch("src.scheduler.send_due_emails") as mock_send:
            # Start scheduler
            await scheduler.start()
            
            # Wait for multiple dispatch cycles (with shorter intervals for testing)
            await asyncio.sleep(0.3)
            
            # Stop scheduler
            await scheduler.stop()
            
            # Should have been called at least once
            assert mock_send.call_count >= 1 