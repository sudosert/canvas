"""Persistent thumbnail cache on disk."""
import os
import hashlib
from pathlib import Path
from typing import Optional
from PIL import Image


class ThumbnailPersistence:
    """Manages persistent thumbnail cache on disk."""
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize thumbnail persistence.
        
        Args:
            cache_dir: Directory to store thumbnails. Defaults to ~/.cache/sd-image-viewer/thumbnails
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/sd-image-viewer/thumbnails")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnail_size = (200, 200)
    
    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key based on file path and modification time."""
        try:
            stat = os.stat(file_path)
            # Use file path + modification time as key
            key_data = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
            return hashlib.md5(key_data.encode()).hexdigest()
        except:
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def _get_cache_path(self, file_path: str) -> Path:
        """Get the cache file path for an image."""
        cache_key = self._get_cache_key(file_path)
        # Use first 2 chars as subdir for better filesystem performance
        subdir = self.cache_dir / cache_key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{cache_key}.png"
    
    def get_thumbnail(self, file_path: str) -> Optional[Image.Image]:
        """
        Get thumbnail from cache if it exists and is valid.
        
        Args:
            file_path: Path to the original image
            
        Returns:
            PIL Image if cached thumbnail exists, None otherwise
        """
        cache_path = self._get_cache_path(file_path)
        
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except:
                # Cache file corrupted, remove it
                cache_path.unlink(missing_ok=True)
        
        return None
    
    def save_thumbnail(self, file_path: str, image: Image.Image) -> bool:
        """
        Save thumbnail to cache.
        
        Args:
            file_path: Path to the original image
            image: PIL Image to cache (will be resized to thumbnail size)
            
        Returns:
            True if saved successfully
        """
        try:
            cache_path = self._get_cache_path(file_path)
            
            # Resize to thumbnail size
            thumb = image.copy()
            thumb.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            
            # Save as PNG
            thumb.save(cache_path, "PNG")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save thumbnail cache: {e}")
            return False
    
    def clear_cache(self) -> int:
        """
        Clear all cached thumbnails.
        
        Returns:
            Number of files removed
        """
        count = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for file in subdir.iterdir():
                    if file.is_file():
                        file.unlink()
                        count += 1
                subdir.rmdir()
        return count
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        total_size = 0
        file_count = 0
        
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for file in subdir.iterdir():
                    if file.is_file():
                        total_size += file.stat().st_size
                        file_count += 1
        
        return {
            'file_count': file_count,
            'total_size_mb': total_size / (1024 * 1024)
        }
