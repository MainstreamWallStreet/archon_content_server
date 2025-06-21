"""
Tests for Pydantic models.
"""

import pytest
from pydantic import ValidationError

from src.models import Item, ItemCreate, ItemUpdate


class TestItem:
    """Test Item model."""

    def test_item_creation_valid(self):
        """Test creating a valid Item."""
        item = Item(
            id="test-1",
            name="Test Item",
            description="A test item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert item.id == "test-1"
        assert item.name == "Test Item"
        assert item.description == "A test item"
        assert item.created_at == "2024-01-01T00:00:00Z"
        assert item.updated_at == "2024-01-01T00:00:00Z"

    def test_item_creation_missing_required_fields(self):
        """Test Item creation with missing required fields."""
        with pytest.raises(ValidationError):
            Item(name="Test Item", description="A test item")

    def test_item_optional_description(self):
        """Test Item creation with optional description."""
        item = Item(
            id="test-1",
            name="Test Item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert item.description is None

    def test_item_json_serialization(self):
        """Test Item JSON serialization."""
        item = Item(
            id="test-1",
            name="Test Item",
            description="A test item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        item_dict = item.model_dump()
        assert item_dict["id"] == "test-1"
        assert item_dict["name"] == "Test Item"
        assert item_dict["description"] == "A test item"


class TestItemCreate:
    """Test ItemCreate model."""

    def test_item_create_valid(self):
        """Test creating a valid ItemCreate."""
        item_create = ItemCreate(name="New Item", description="A new item")

        assert item_create.name == "New Item"
        assert item_create.description == "A new item"

    def test_item_create_missing_name(self):
        """Test ItemCreate with missing required name."""
        with pytest.raises(ValidationError):
            ItemCreate(description="A new item")

    def test_item_create_optional_description(self):
        """Test ItemCreate with optional description."""
        item_create = ItemCreate(name="New Item")

        assert item_create.description is None

    def test_item_create_empty_name(self):
        """Test ItemCreate with empty name."""
        with pytest.raises(ValidationError):
            ItemCreate(name="")

    def test_item_create_long_name(self):
        """Test ItemCreate with very long name."""
        long_name = "a" * 256  # Exceeds max length
        with pytest.raises(ValidationError):
            ItemCreate(name=long_name)


class TestItemUpdate:
    """Test ItemUpdate model."""

    def test_item_update_valid(self):
        """Test creating a valid ItemUpdate."""
        item_update = ItemUpdate(name="Updated Item", description="An updated item")

        assert item_update.name == "Updated Item"
        assert item_update.description == "An updated item"

    def test_item_update_partial(self):
        """Test ItemUpdate with partial fields."""
        item_update = ItemUpdate(name="Updated Item")

        assert item_update.name == "Updated Item"
        assert item_update.description is None

    def test_item_update_empty(self):
        """Test ItemUpdate with no fields."""
        item_update = ItemUpdate()

        assert item_update.name is None
        assert item_update.description is None

    def test_item_update_json_serialization(self):
        """Test ItemUpdate JSON serialization."""
        item_update = ItemUpdate(name="Updated Item", description="An updated item")

        item_dict = item_update.model_dump(exclude_none=True)
        assert item_dict["name"] == "Updated Item"
        assert item_dict["description"] == "An updated item"
