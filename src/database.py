"""
Data store interface for FastAPI template.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.models import Item, ItemCreate, ItemUpdate


class DataStore(ABC):
    """Abstract interface for data storage."""

    @abstractmethod
    def list_items(self) -> List[Item]:
        """List all items."""
        pass

    @abstractmethod
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get a specific item by ID."""
        pass

    @abstractmethod
    def create_item(self, item: ItemCreate) -> Item:
        """Create a new item."""
        pass

    @abstractmethod
    def update_item(self, item_id: str, item: ItemUpdate) -> Item:
        """Update an existing item."""
        pass

    @abstractmethod
    def delete_item(self, item_id: str) -> None:
        """Delete an item."""
        pass

    def list_objects(self) -> list:
        raise NotImplementedError

    def get_object(self, object_name: str) -> bytes:
        raise NotImplementedError

    def put_object(self, object_name: str, data: bytes) -> None:
        raise NotImplementedError

    def update_object(self, object_name: str, data: bytes) -> None:
        raise NotImplementedError

    def delete_object(self, object_name: str) -> None:
        raise NotImplementedError
