"""Data model for image collections."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os
from pathlib import Path


@dataclass
class Collection:
    """Represents a collection of images based on filter criteria."""
    
    name: str
    include_terms: List[str] = field(default_factory=list)
    exclude_terms: List[str] = field(default_factory=list)
    sort_by: str = 'date'
    reverse_sort: bool = False
    thumbnail_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert collection to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Collection':
        """Create collection from dictionary."""
        return cls(**data)
    
    def matches_filters(self, include_terms: List[str], exclude_terms: List[str]) -> bool:
        """Check if this collection matches the given filter criteria."""
        return (
            set(self.include_terms) == set(include_terms) and
            set(self.exclude_terms) == set(exclude_terms)
        )


class CollectionsManager:
    """Manages persistence of collections."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize collections manager.
        
        Args:
            storage_path: Path to store collections JSON file.
                         Defaults to ~/.config/sd-image-viewer/collections.json
        """
        if storage_path is None:
            storage_path = os.path.expanduser("~/.config/sd-image-viewer/collections.json")
        
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._collections: List[Collection] = []
        self._load_collections()
    
    def _load_collections(self):
        """Load collections from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._collections = [Collection.from_dict(c) for c in data.get('collections', [])]
                print(f"[DEBUG] Loaded {len(self._collections)} collections")
            except Exception as e:
                print(f"[ERROR] Failed to load collections: {e}")
                self._collections = []
        else:
            self._collections = []
    
    def _save_collections(self):
        """Save collections to storage."""
        try:
            data = {
                'version': 1,
                'collections': [c.to_dict() for c in self._collections]
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[DEBUG] Saved {len(self._collections)} collections")
        except Exception as e:
            print(f"[ERROR] Failed to save collections: {e}")
    
    def get_all_collections(self) -> List[Collection]:
        """Get all collections sorted alphabetically by name."""
        return sorted(self._collections, key=lambda c: c.name.lower())
    
    def get_collection(self, name: str) -> Optional[Collection]:
        """Get a collection by name."""
        for collection in self._collections:
            if collection.name == name:
                return collection
        return None
    
    def add_collection(self, collection: Collection) -> bool:
        """
        Add a new collection.
        
        Args:
            collection: Collection to add
            
        Returns:
            True if added successfully, False if name already exists
        """
        if self.get_collection(collection.name) is not None:
            return False
        
        self._collections.append(collection)
        self._save_collections()
        return True
    
    def update_collection(self, name: str, **kwargs) -> bool:
        """
        Update a collection's properties.
        
        Args:
            name: Name of collection to update
            **kwargs: Properties to update
            
        Returns:
            True if updated successfully
        """
        collection = self.get_collection(name)
        if collection is None:
            return False
        
        for key, value in kwargs.items():
            if hasattr(collection, key):
                setattr(collection, key, value)
        
        collection.updated_at = datetime.now().isoformat()
        self._save_collections()
        return True
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.
        
        Args:
            name: Name of collection to delete
            
        Returns:
            True if deleted successfully
        """
        collection = self.get_collection(name)
        if collection is None:
            return False
        
        self._collections.remove(collection)
        self._save_collections()
        return True
    
    def create_from_filters(
        self,
        name: str,
        include_terms: List[str],
        exclude_terms: List[str],
        sort_by: str = 'date',
        reverse_sort: bool = False,
        thumbnail_path: Optional[str] = None
    ) -> Optional[Collection]:
        """
        Create a new collection from filter criteria.
        
        Args:
            name: Collection name
            include_terms: Terms to include in filter
            exclude_terms: Terms to exclude in filter
            sort_by: Sort field
            reverse_sort: Whether to reverse sort
            thumbnail_path: Path to thumbnail image
            
        Returns:
            Created collection or None if name already exists
        """
        if self.get_collection(name) is not None:
            return None
        
        collection = Collection(
            name=name,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            sort_by=sort_by,
            reverse_sort=reverse_sort,
            thumbnail_path=thumbnail_path
        )
        
        self._collections.append(collection)
        self._save_collections()
        return collection
    
    def set_thumbnail(self, collection_name: str, image_path: str) -> bool:
        """
        Set the thumbnail for a collection.
        
        Args:
            collection_name: Name of collection
            image_path: Path to image to use as thumbnail
            
        Returns:
            True if set successfully
        """
        return self.update_collection(collection_name, thumbnail_path=image_path)
    
    def rename_collection(self, old_name: str, new_name: str) -> bool:
        """
        Rename a collection.
        
        Args:
            old_name: Current name of the collection
            new_name: New name for the collection
            
        Returns:
            True if renamed successfully, False if old_name doesn't exist
            or new_name already exists
        """
        if old_name == new_name:
            return True
        
        collection = self.get_collection(old_name)
        if collection is None:
            return False
        
        if self.get_collection(new_name) is not None:
            return False
        
        collection.name = new_name
        collection.updated_at = datetime.now().isoformat()
        self._save_collections()
        return True
