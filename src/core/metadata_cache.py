"""Persistent metadata cache for fast loading of image collections."""
import json
import hashlib
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.image_data import ImageMetadata


class MetadataCache:
    """
    Manages persistent metadata cache stored as JSON files.
    
    Cache is stored per-folder in ~/.cache/sd-image-viewer/metadata/
    Each folder gets a cache file named after the folder's hash.
    """
    
    CACHE_VERSION = 1  # For future compatibility
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize metadata cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.cache/sd-image-viewer/metadata
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/sd-image-viewer/metadata")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_folder_hash(self, folder_path: str) -> str:
        """Generate a hash for the folder path."""
        return hashlib.sha256(folder_path.encode()).hexdigest()[:16]
    
    def _get_cache_file(self, folder_path: str) -> Path:
        """Get the cache file path for a folder."""
        folder_hash = self._get_folder_hash(folder_path)
        return self.cache_dir / f"{folder_hash}.json"
    
    def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute a quick hash of file metadata (not content) for change detection.
        Uses file path, size, and modification time.
        """
        try:
            stat = os.stat(file_path)
            hash_data = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.sha256(hash_data.encode()).hexdigest()[:16]
        except:
            return ""
    
    def load_cache(self, folder_path: str) -> Optional[List[ImageMetadata]]:
        """
        Load cached metadata for a folder if available and valid.
        
        Args:
            folder_path: Path to the image folder
            
        Returns:
            List of ImageMetadata if cache is valid, None otherwise
        """
        cache_file = self._get_cache_file(folder_path)
        
        if not cache_file.exists():
            print(f"[DEBUG] No cache file found for {folder_path}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check cache version
            if cache_data.get('version') != self.CACHE_VERSION:
                print(f"[DEBUG] Cache version mismatch, rebuilding")
                return None
            
            # Check if folder path matches
            if cache_data.get('folder_path') != folder_path:
                print(f"[DEBUG] Cache folder path mismatch, rebuilding")
                return None
            
            # Verify all files are still valid
            cached_files = cache_data.get('files', {})
            current_files = self._scan_folder_files(folder_path)
            
            # Check for new, modified, or deleted files
            if set(cached_files.keys()) != set(current_files.keys()):
                print(f"[DEBUG] File list changed, cache invalid")
                return None
            
            # Check each file's hash
            for file_path, current_hash in current_files.items():
                cached_entry = cached_files.get(file_path)
                if not cached_entry:
                    print(f"[DEBUG] Missing cache entry for {file_path}")
                    return None
                
                cached_hash = cached_entry.get('file_hash', '')
                if cached_hash != current_hash:
                    print(f"[DEBUG] File changed: {file_path}")
                    return None
            
            # Cache is valid, reconstruct metadata
            metadata_list = []
            for file_path, entry in cached_files.items():
                data = entry.get('metadata', {})
                metadata = ImageMetadata.from_dict(data)
                metadata_list.append(metadata)
            
            print(f"[DEBUG] Loaded {len(metadata_list)} images from cache")
            return metadata_list
            
        except Exception as e:
            print(f"[ERROR] Failed to load cache: {e}")
            return None
    
    def save_cache(self, folder_path: str, metadata_list: List[ImageMetadata]) -> bool:
        """
        Save metadata to cache file.
        
        Args:
            folder_path: Path to the image folder
            metadata_list: List of ImageMetadata to cache
            
        Returns:
            True if saved successfully
        """
        try:
            cache_file = self._get_cache_file(folder_path)
            
            # Build cache structure
            files_cache = {}
            for metadata in metadata_list:
                file_hash = self._compute_file_hash(metadata.file_path)
                files_cache[metadata.file_path] = {
                    'file_hash': file_hash,
                    'metadata': metadata.to_dict()
                }
            
            cache_data = {
                'version': self.CACHE_VERSION,
                'folder_path': folder_path,
                'cached_at': datetime.now().isoformat(),
                'file_count': len(metadata_list),
                'files': files_cache
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"[DEBUG] Saved cache with {len(metadata_list)} images")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save cache: {e}")
            return False
    
    def clear_cache(self, folder_path: str = None) -> bool:
        """
        Clear cache for a specific folder or all caches.
        
        Args:
            folder_path: If provided, only clear cache for this folder.
                        If None, clear all caches.
                        
        Returns:
            True if cleared successfully
        """
        try:
            if folder_path:
                cache_file = self._get_cache_file(folder_path)
                if cache_file.exists():
                    cache_file.unlink()
                    print(f"[DEBUG] Cleared cache for {folder_path}")
            else:
                # Clear all cache files
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                print(f"[DEBUG] Cleared all caches")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to clear cache: {e}")
            return False
    
    def _scan_folder_files(self, folder_path: str) -> Dict[str, str]:
        """
        Scan folder and return dict of file paths to their hashes.
        
        Args:
            folder_path: Path to scan
            
        Returns:
            Dict mapping file paths to file hashes
        """
        files = {}
        folder = Path(folder_path)
        
        if not folder.exists():
            return files
        
        for ext in ['*.png', '*.jpg', '*.jpeg']:
            for file_path in folder.rglob(ext):
                if file_path.is_file():
                    file_hash = self._compute_file_hash(str(file_path))
                    files[str(file_path)] = file_hash
        
        return files
    
    def get_cache_stats(self, folder_path: str = None) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Args:
            folder_path: If provided, get stats for specific folder.
                        If None, get stats for all caches.
                        
        Returns:
            Dict with cache statistics
        """
        if folder_path:
            cache_file = self._get_cache_file(folder_path)
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return {
                        'exists': True,
                        'file_count': data.get('file_count', 0),
                        'cached_at': data.get('cached_at', 'unknown'),
                        'size_kb': cache_file.stat().st_size / 1024
                    }
                except:
                    return {'exists': True, 'error': 'corrupted'}
            return {'exists': False}
        else:
            # Global stats
            total_size = 0
            cache_count = 0
            total_files = 0
            
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    total_files += data.get('file_count', 0)
                    total_size += cache_file.stat().st_size
                    cache_count += 1
                except:
                    pass
            
            return {
                'cache_count': cache_count,
                'total_files_cached': total_files,
                'total_size_mb': total_size / (1024 * 1024)
            }
