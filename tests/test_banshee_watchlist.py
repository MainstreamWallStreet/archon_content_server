import unittest
from unittest.mock import patch, MagicMock
from src.banshee_watchlist import BansheeStore

class TestBansheeStore(unittest.TestCase):
    def setUp(self):
        self.store = BansheeStore("test-bucket")

    @patch('src.notifications.send_alert')
    def test_add_ticker_sends_notification(self, mock_send_alert):
        self.store.add_ticker("AAPL", "test_user")
        mock_send_alert.assert_called_once()

    @patch('src.notifications.send_alert')
    def test_remove_ticker_sends_notification(self, mock_send_alert):
        self.store.remove_ticker("AAPL")
        mock_send_alert.assert_called_once()

if __name__ == '__main__':
    unittest.main() 