"""
Tests for data store interface and implementations.
"""

import json
from unittest.mock import MagicMock, patch, mock_open
from typing import List

import pytest
from google.cloud.exceptions import GoogleCloudError
import os

from src.database import DataStore
from src.gcs_store import GcsStore
from src.models import Item, ItemCreate, ItemUpdate


class TestDataStoreInterface:
    """Test the DataStore abstract interface."""
    
    def test_data_store_interface_methods(self):
        """Test that DataStore interface has required methods."""
        # This test ensures the interface is properly defined
        assert hasattr(DataStore, 'list_items')
        assert hasattr(DataStore, 'get_item')
        assert hasattr(DataStore, 'create_item')
        assert hasattr(DataStore, 'update_item')
        assert hasattr(DataStore, 'delete_item')


class TestGcsStore:
    """Test GCS-based data store implementation."""
    
    def test_gcs_store_initialization_valid_bucket(self):
        """Test GCS store initialization with valid bucket."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            assert store.bucket_name == "test-bucket"
    
    def test_gcs_store_initialization_empty_bucket(self):
        """Test GCS store initialization with empty bucket name."""
        with pytest.raises(ValueError, match="Bucket name is required"):
            GcsStore("")
    
    def test_gcs_store_initialization_none_bucket(self):
        """Test GCS store initialization with None bucket name."""
        with pytest.raises(ValueError, match="Bucket name is required"):
            GcsStore(None)
    
    def test_gcs_store_initialization_bucket_not_exists(self):
        """Test GCS store initialization with non-existent bucket."""
        with patch("src.gcs_store.storage.Client") as mock_client, \
             patch("os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "DEBUG": "false",
                "GOOGLE_APPLICATION_CREDENTIALS": "/some/fake/path.json"
            }.get(key, default)
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = False
            mock_client.return_value.bucket.return_value = mock_bucket
            
            with pytest.raises(RuntimeError, match="Failed to initialize GCS client"):
                GcsStore("test-bucket", force_gcs=True)
    
    def test_gcs_store_initialization_gcs_error(self):
        """Test GCS store initialization with GCS client error."""
        with patch("src.gcs_store.storage.Client") as mock_client, \
             patch("os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "DEBUG": "false",
                "GOOGLE_APPLICATION_CREDENTIALS": "/some/fake/path.json"
            }.get(key, default)
            mock_client.side_effect = GoogleCloudError("GCS error")
            
            with pytest.raises(RuntimeError, match="Failed to initialize GCS client"):
                GcsStore("test-bucket", force_gcs=True)
    
    def test_list_items_empty_bucket(self):
        """Test listing items from empty bucket."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            items = store.list_items()
            assert items == []
    
    def test_list_items_with_data(self):
        """Test listing items with existing data."""
        sample_items = [
            {
                "id": "item-1",
                "name": "Test Item 1",
                "description": "First item",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "item-2",
                "name": "Test Item 2",
                "description": "Second item",
                "created_at": "2024-01-02T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z"
            }
        ]
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_blob.download_as_text.return_value = json.dumps({"items": sample_items})
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            items = store.list_items()
            
            assert len(items) == 2
            assert items[0].id == "item-1"
            assert items[1].id == "item-2"
    
    def test_list_items_gcs_error(self):
        """Test listing items with GCS error."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_blob.download_as_text.side_effect = GoogleCloudError("Download error")
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            with pytest.raises(RuntimeError, match="Failed to list items"):
                store.list_items()
    
    def test_get_item_exists(self):
        """Test getting an existing item."""
        sample_item = {
            "id": "item-1",
            "name": "Test Item",
            "description": "A test item",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_blob.download_as_text.return_value = json.dumps(sample_item)
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            item = store.get_item("item-1")
            
            assert item.id == "item-1"
            assert item.name == "Test Item"
    
    def test_get_item_not_exists(self):
        """Test getting a non-existent item."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            item = store.get_item("non-existent")
            assert item is None
    
    def test_create_item_success(self):
        """Test creating a new item."""
        item_create = ItemCreate(name="New Item", description="A new item")
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False  # Item doesn't exist yet
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            item = store.create_item(item_create)
            
            assert item.name == "New Item"
            assert item.description == "A new item"
            assert item.id is not None
            assert item.created_at is not None
            assert item.updated_at is not None
            
            # Verify the item was saved
            mock_blob.upload_from_string.assert_called_once()
    
    def test_create_item_already_exists(self):
        """Test creating an item that already exists."""
        item_create = ItemCreate(name="Existing Item", description="An existing item")
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True  # Item already exists
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            with pytest.raises(ValueError, match="Item with id .* already exists"):
                store.create_item(item_create)
    
    def test_update_item_success(self):
        """Test updating an existing item."""
        existing_item = {
            "id": "item-1",
            "name": "Old Name",
            "description": "Old description",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        item_update = ItemUpdate(name="New Name", description="New description")
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_blob.download_as_text.return_value = json.dumps(existing_item)
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            item = store.update_item("item-1", item_update)
            
            assert item.name == "New Name"
            assert item.description == "New description"
            assert item.id == "item-1"
            assert item.created_at == "2024-01-01T00:00:00Z"
            # updated_at should be different
            assert item.updated_at != "2024-01-01T00:00:00Z"
    
    def test_update_item_not_exists(self):
        """Test updating a non-existent item."""
        item_update = ItemUpdate(name="New Name")
        
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            with pytest.raises(ValueError, match="Item with id .* not found"):
                store.update_item("non-existent", item_update)
    
    def test_delete_item_success(self):
        """Test deleting an existing item."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            store.delete_item("item-1")
            
            # Verify the blob was deleted
            mock_blob.delete.assert_called_once()
    
    def test_delete_item_not_exists(self):
        """Test deleting a non-existent item."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = False
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            with pytest.raises(ValueError, match="Item with id .* not found"):
                store.delete_item("non-existent")
    
    def test_delete_item_gcs_error(self):
        """Test deleting item with GCS error."""
        with patch("src.gcs_store.storage.Client") as mock_client:
            mock_bucket = MagicMock()
            mock_bucket.exists.return_value = True
            mock_blob = MagicMock()
            mock_blob.exists.return_value = True
            mock_blob.delete.side_effect = GoogleCloudError("Delete error")
            mock_bucket.blob.return_value = mock_blob
            mock_client.return_value.bucket.return_value = mock_bucket
            
            store = GcsStore("test-bucket")
            with pytest.raises(RuntimeError, match="Failed to delete item"):
                store.delete_item("item-1") 