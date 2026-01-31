"""Image caching utilities for efficient thumbnail and preview loading."""
from typing import Dict, Optional, Tuple
from pathlib import Path
from PIL import Image
from PyQt6.QtGui import QPixmap, QImage
import io


class ImageCache:
    """LRU cache for loaded images with size limits."""
    
    def __init__(self, max_cache_size: int = 100, max_memory_mb: int = 200):
        """
        Initialize the image cache.
        
        Args:
            max_cache_size: Maximum number of images to cache
            max_memory_mb: Maximum memory usage in MB
        """
        self.max_cache_size = max_cache_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._cache: Dict[str, Dict] = {}
        self._access_order: list = []
        self._current_memory = 0
    
    def get(self, file_path: str, size: Optional[Tuple[int, int]] = None) -> Optional[QPixmap]:
        """
        Get an image from cache or load it.
        
        Args:
            file_path: Path to the image file
            size: Optional (width, height) to resize to
            
        Returns:
            QPixmap or None if loading failed
        """
        cache_key = f"{file_path}_{size}"
        
        # Check if in cache
        if cache_key in self._cache:
            self._update_access_order(cache_key)
            return self._cache[cache_key]['pixmap']
        
        # Load the image
        pixmap = self._load_image(file_path, size)
        if pixmap:
            self._add_to_cache(cache_key, pixmap)
        
        return pixmap
    
    def _load_image(self, file_path: str, size: Optional[Tuple[int, int]]) -> Optional[QPixmap]:
        """Load an image from disk."""
        try:
            print(f"[DEBUG] Loading image: {file_path}")
            # Use PIL to load and optionally resize
            with Image.open(file_path) as img:
                print(f"[DEBUG] Image mode: {img.mode}, size: {img.size}")
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P', 'LA', 'L'):
                    img = img.convert('RGB')
                elif img.mode not in ('RGB',):
                    img = img.convert('RGB')
                
                # Resize if requested
                if size:
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Convert to QPixmap
                data = io.BytesIO()
                img.save(data, format='PNG')
                data.seek(0)
                
                qimg = QImage.fromData(data.getvalue())
                if qimg.isNull():
                    print(f"[ERROR] QImage is null for {file_path}")
                    return None
                pixmap = QPixmap.fromImage(qimg)
                print(f"[DEBUG] Successfully loaded image, pixmap size: {pixmap.width()}x{pixmap.height()}")
                return pixmap
                
        except Exception as e:
            import traceback
            print(f"[ERROR] Error loading image {file_path}: {e}")
            print(traceback.format_exc())
            return None
    
    def _add_to_cache(self, cache_key: str, pixmap: QPixmap) -> None:
        """Add an image to the cache with LRU eviction."""
        # Calculate memory usage (rough estimate)
        memory_usage = pixmap.width() * pixmap.height() * 4  # 4 bytes per pixel (RGBA)
        
        # Evict entries if necessary
        while (len(self._cache) >= self.max_cache_size or 
               self._current_memory + memory_usage > self.max_memory_bytes):
            if not self._access_order:
                break
            self._evict_oldest()
        
        # Add to cache
        self._cache[cache_key] = {
            'pixmap': pixmap,
            'memory': memory_usage
        }
        self._current_memory += memory_usage
        self._access_order.append(cache_key)
    
    def _evict_oldest(self) -> None:
        """Remove the least recently used item from cache."""
        if not self._access_order:
            return
        
        oldest_key = self._access_order.pop(0)
        if oldest_key in self._cache:
            self._current_memory -= self._cache[oldest_key]['memory']
            del self._cache[oldest_key]
    
    def _update_access_order(self, cache_key: str) -> None:
        """Move accessed key to end of access order (most recent)."""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._access_order.clear()
        self._current_memory = 0
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            'cached_images': len(self._cache),
            'memory_usage_mb': self._current_memory / (1024 * 1024),
            'max_memory_mb': self.max_memory_bytes / (1024 * 1024)
        }


class ThumbnailCache(ImageCache):
    """Specialized cache for thumbnails with fixed size."""
    
    def __init__(self, thumbnail_size: Tuple[int, int] = (200, 200), max_cache_size: int = 500):
        """
        Initialize thumbnail cache.
        
        Args:
            thumbnail_size: Default (width, height) for thumbnails
            max_cache_size: Maximum number of thumbnails to cache
        """
        super().__init__(max_cache_size=max_cache_size, max_memory_mb=300)
        self.thumbnail_size = thumbnail_size
    
    def get_thumbnail(self, file_path: str) -> Optional[QPixmap]:
        """Get a thumbnail for an image."""
        return self.get(file_path, self.thumbnail_size)
