from __future__ import annotations

"""
In-memory implementation of the `DataStore` interface.
This replaces the previous GCS-backed store and is intended for
local development / simple deployments where persistence is not
required.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.database import DataStore
from src.models import Item, ItemCreate, ItemUpdate


class InMemoryStore(DataStore):
    """A thread-safe in-memory store for `Item` resources."""

    def __init__(self):
        # item_id → Item
        self._items: Dict[str, Item] = {}

    # ────────────────────────────────
    # Item helpers
    # ────────────────────────────────
    def list_items(self) -> List[Item]:
        return list(self._items.values())

    def get_item(self, item_id: str) -> Optional[Item]:
        return self._items.get(item_id)

    def create_item(self, item: ItemCreate) -> Item:
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        new_item = Item(
            id=item_id,
            name=item.name,
            description=item.description,
            created_at=now,
            updated_at=now,
        )
        self._items[item_id] = new_item
        return new_item

    def update_item(self, item_id: str, item_update: ItemUpdate) -> Item:
        if item_id not in self._items:
            raise ValueError(f"Item with id {item_id} not found")

        existing = self._items[item_id]
        for field, value in item_update.model_dump(exclude_none=True).items():
            setattr(existing, field, value)
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        self._items[item_id] = existing
        return existing

    def delete_item(self, item_id: str) -> None:
        if item_id not in self._items:
            raise ValueError(f"Item with id {item_id} not found")
        del self._items[item_id]
