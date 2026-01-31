"""Asynchronous folder loading worker."""
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Optional

from ..core.image_scanner import ImageScanner
from ..core.metadata_cache import MetadataCache
from ..models.image_data import ImageMetadata


class FolderLoaderThread(QThread):
    """Worker thread for loading images from a folder."""
    
    # Signals
    progress_update = pyqtSignal(int, int, str)  # current, total, message
    loading_complete = pyqtSignal(list)  # List[ImageMetadata]
    loading_failed = pyqtSignal(str)  # error message
    
    def __init__(self, folder: str, use_cache: bool = False, skip_validation: bool = False, recursive: bool = True):
        super().__init__()
        self.folder = folder
        self.use_cache = use_cache
        self.skip_validation = skip_validation
        self.recursive = recursive
        self._cancelled = False
        
    def run(self):
        """Run the loading process."""
        try:
            images = None
            metadata_cache = MetadataCache()
            
            # Try to load from cache if enabled
            if self.use_cache or self.skip_validation:
                self.progress_update.emit(0, 0, "Loading from cache...")
                cached_images = metadata_cache.load_cache(self.folder, skip_validation=self.skip_validation)
                if cached_images is not None:
                    images = cached_images
                    self.progress_update.emit(len(images), len(images), f"Loaded {len(images)} images from cache")
            
            # If not cached and not skipping updates, scan the directory
            if images is None and not self.skip_validation:
                self.progress_update.emit(0, 0, "Scanning folder...")
                
                def progress_callback(current, total):
                    if self._cancelled:
                        return False
                    self.progress_update.emit(current, total, f"Scanning images... {current}/{total}")
                    return True
                
                scanner = ImageScanner(progress_callback=progress_callback)
                images = scanner.scan_directory(self.folder, recursive=self.recursive)
                
                # Save to cache if enabled
                if self.use_cache and not self._cancelled:
                    self.progress_update.emit(0, 0, "Saving to cache...")
                    metadata_cache.save_cache(self.folder, images)
            
            # If skipping updates and no cache, error
            if images is None and self.skip_validation:
                self.loading_failed.emit("No cached data available for this folder.\n\nRun without --skip-db-update first to build the cache.")
                return
            
            if not self._cancelled:
                self.loading_complete.emit(images)
                
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            self.loading_failed.emit(error_msg)
    
    def cancel(self):
        """Cancel the loading process."""
        self._cancelled = True
