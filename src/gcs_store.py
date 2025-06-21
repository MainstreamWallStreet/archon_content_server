"""
GCS-based data store implementation.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import io
import os

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from src.database import DataStore
from src.models import Item, ItemCreate, ItemUpdate


class MockStore(DataStore):
    """In-memory mock store for local development."""
    
    def __init__(self, bucket_name: str):
        """Initialize mock store."""
        self.bucket_name = bucket_name
        self.items = {}  # item_id -> Item
        self.objects = {}  # object_name -> bytes
    
    def list_items(self) -> List[Item]:
        """List all items from mock store."""
        return list(self.items.values())
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get a specific item by ID from mock store."""
        return self.items.get(item_id)
    
    def create_item(self, item: ItemCreate) -> Item:
        """Create a new item in mock store."""
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        new_item = Item(
            id=item_id,
            name=item.name,
            description=item.description,
            created_at=now,
            updated_at=now
        )
        
        if item_id in self.items:
            raise ValueError(f"Item with id {item_id} already exists")
        
        self.items[item_id] = new_item
        return new_item
    
    def update_item(self, item_id: str, item_update: ItemUpdate) -> Item:
        """Update an existing item in mock store."""
        if item_id not in self.items:
            raise ValueError(f"Item with id {item_id} not found")
        
        existing_item = self.items[item_id]
        
        # Update fields
        update_data = item_update.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(existing_item, field, value)
        
        # Update timestamp
        existing_item.updated_at = datetime.now(timezone.utc).isoformat()
        
        self.items[item_id] = existing_item
        return existing_item
    
    def delete_item(self, item_id: str) -> None:
        """Delete an item from mock store."""
        if item_id not in self.items:
            raise ValueError(f"Item with id {item_id} not found")
        
        del self.items[item_id]

    def list_objects(self) -> List[str]:
        """List all object names in the mock store."""
        return list(self.objects.keys())

    def get_object(self, object_name: str) -> bytes:
        """Download an object from the mock store."""
        if object_name not in self.objects:
            raise FileNotFoundError(f"Object {object_name} not found.")
        return self.objects[object_name]

    def put_object(self, object_name: str, data: bytes) -> None:
        """Upload a new object to the mock store."""
        if object_name in self.objects:
            raise FileExistsError(f"Object {object_name} already exists.")
        self.objects[object_name] = data

    def update_object(self, object_name: str, data: bytes) -> None:
        """Update (overwrite) an existing object in the mock store."""
        if object_name not in self.objects:
            raise FileNotFoundError(f"Object {object_name} not found.")
        self.objects[object_name] = data

    def delete_object(self, object_name: str) -> None:
        """Delete an object from the mock store."""
        if object_name not in self.objects:
            raise FileNotFoundError(f"Object {object_name} not found.")
        del self.objects[object_name]


class GcsStore(DataStore):
    """GCS-based implementation of DataStore."""
    
    def __init__(self, bucket_name: str, force_gcs: bool = False):
        """Initialize GCS store with bucket name."""
        if not bucket_name:
            raise ValueError("Bucket name is required")
        
        # Check if we're in local development mode (no valid GCP credentials)
        if not force_gcs and (os.getenv("DEBUG", "false").lower() == "true" or not os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
            print("⚠️  Using mock store for local development")
            self._store = MockStore(bucket_name)
            return
        
        try:
            # Handle case where GOOGLE_APPLICATION_CREDENTIALS contains JSON content directly
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and creds_path.startswith('{'):
                import json
                import tempfile
                try:
                    creds_data = json.loads(creds_path)
                    print(f"✅ Successfully parsed JSON credentials")
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    import base64
                    try:
                        padding = 4 - (len(creds_path) % 4)
                        if padding != 4:
                            creds_path += '=' * padding
                        decoded = base64.b64decode(creds_path).decode('utf-8')
                        creds_data = json.loads(decoded)
                        print(f"✅ Successfully decoded base64 credentials")
                    except Exception as e:
                        print(f"⚠️  Failed to decode credentials: {e}")
                        print(f"📄 Credentials length: {len(creds_path)}")
                        print(f"📄 First 100 chars: {creds_path[:100]}")
                        raise
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(creds_data, f)
                    temp_creds_path = f.name
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_creds_path
                print(f"📁 Created temporary credentials file: {temp_creds_path}")
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
            self.bucket_name = bucket_name
            self._store = None
            # Only check bucket existence if force_gcs is True (for tests)
            if force_gcs and not self.bucket.exists():
                raise ValueError(f"GCS bucket {bucket_name} does not exist")
            print(f"✅ GCS store initialized with bucket: {bucket_name}")
        except Exception as e:
            if force_gcs:
                raise RuntimeError("Failed to initialize GCS client") from e
            print(f"⚠️  GCS initialization failed, using mock store: {e}")
            self._store = MockStore(bucket_name)
    
    def _get_store(self):
        """Get the appropriate store implementation."""
        if hasattr(self, '_store') and self._store is not None:
            return self._store
        return self
    
    def list_items(self) -> List[Item]:
        """List all items from GCS."""
        store = self._get_store()
        if store != self:
            return store.list_items()
            
        try:
            blob = self.bucket.blob("items.json")
            if not blob.exists():
                return []
            
            data = json.loads(blob.download_as_text())
            return [Item(**item) for item in data.get("items", [])]
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to list items: {exc}") from exc
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get a specific item by ID from GCS."""
        store = self._get_store()
        if store != self:
            return store.get_item(item_id)
            
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                return None
            
            data = json.loads(blob.download_as_text())
            return Item(**data)
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to get item {item_id}: {exc}") from exc
    
    def create_item(self, item: ItemCreate) -> Item:
        """Create a new item in GCS."""
        store = self._get_store()
        if store != self:
            return store.create_item(item)
            
        try:
            item_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            new_item = Item(
                id=item_id,
                name=item.name,
                description=item.description,
                created_at=now,
                updated_at=now
            )
            
            # Check if item with this ID already exists (unlikely but possible)
            blob = self.bucket.blob(f"items/{item_id}.json")
            if blob.exists():
                raise ValueError(f"Item with id {item_id} already exists")
            
            # Save the item
            blob.upload_from_string(
                json.dumps(new_item.model_dump()),
                content_type="application/json"
            )
            
            return new_item
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to create item: {exc}") from exc
    
    def update_item(self, item_id: str, item_update: ItemUpdate) -> Item:
        """Update an existing item in GCS."""
        store = self._get_store()
        if store != self:
            return store.update_item(item_id, item_update)
            
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                raise ValueError(f"Item with id {item_id} not found")
            
            # Get existing item
            existing_data = json.loads(blob.download_as_text())
            existing_item = Item(**existing_data)
            
            # Update fields
            update_data = item_update.model_dump(exclude_none=True)
            for field, value in update_data.items():
                setattr(existing_item, field, value)
            
            # Update timestamp
            existing_item.updated_at = datetime.now(timezone.utc).isoformat()
            
            # Save updated item
            blob.upload_from_string(
                json.dumps(existing_item.model_dump()),
                content_type="application/json"
            )
            
            return existing_item
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to update item {item_id}: {exc}") from exc
    
    def delete_item(self, item_id: str) -> None:
        """Delete an item from GCS."""
        store = self._get_store()
        if store != self:
            return store.delete_item(item_id)
            
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                raise ValueError(f"Item with id {item_id} not found")
            
            blob.delete()
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to delete item {item_id}: {exc}") from exc

    def list_objects(self) -> List[str]:
        """
        List all object names in the bucket.
        """
        store = self._get_store()
        if store != self:
            return store.list_objects()
            
        return [blob.name for blob in self.bucket.list_blobs()]

    def get_object(self, object_name: str) -> bytes:
        """
        Download an object from the bucket.
        """
        store = self._get_store()
        if store != self:
            return store.get_object(object_name)
            
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        return blob.download_as_bytes()

    def put_object(self, object_name: str, data: bytes) -> None:
        """
        Upload a new object to the bucket.
        """
        store = self._get_store()
        if store != self:
            return store.put_object(object_name, data)
            
        blob = self.bucket.blob(object_name)
        if blob.exists():
            raise FileExistsError(f"Object {object_name} already exists.")
        blob.upload_from_string(data)

    def update_object(self, object_name: str, data: bytes) -> None:
        """
        Update (overwrite) an existing object in the bucket.
        """
        store = self._get_store()
        if store != self:
            return store.update_object(object_name, data)
            
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        blob.upload_from_string(data)

    def delete_object(self, object_name: str) -> None:
        """
        Delete an object from the bucket.
        """
        store = self._get_store()
        if store != self:
            return store.delete_object(object_name)
            
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        blob.delete() 