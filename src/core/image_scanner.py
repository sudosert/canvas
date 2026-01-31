"""Image scanner for discovering and indexing images in directories."""
import os
from pathlib import Path
from typing import List, Callable, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.image_data import ImageMetadata
from .metadata_parser import MetadataParser


class ImageScanner:
    """Scans directories for Stable Diffusion images and extracts metadata."""
    
    SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    
    def __init__(self, progress_callback: Optional[Callable[[int, int], None]] = None):
        """
        Initialize the scanner.
        
        Args:
            progress_callback: Optional callback(current, total) for progress updates
        """
        self.progress_callback = progress_callback
        self.parser = MetadataParser()
    
    def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
        max_workers: int = 4
    ) -> List[ImageMetadata]:
        """
        Scan a directory for images and extract metadata.
        
        Args:
            directory: Path to directory to scan
            recursive: Whether to scan subdirectories
            max_workers: Number of parallel workers for parsing
            
        Returns:
            List of ImageMetadata objects
        """
        # First, collect all image files
        image_files = self._collect_image_files(directory, recursive)
        
        if not image_files:
            return []
        
        # Parse metadata in parallel
        results = []
        total = len(image_files)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self.parser.parse_image, str(path)): path
                for path in image_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_path):
                try:
                    metadata = future.result()
                    results.append(metadata)
                except Exception as e:
                    path = future_to_path[future]
                    print(f"Error parsing {path}: {e}")
                
                completed += 1
                if self.progress_callback:
                    self.progress_callback(completed, total)
        
        return results
    
    def scan_directory_iter(
        self,
        directory: str,
        recursive: bool = True
    ) -> Iterator[ImageMetadata]:
        """
        Scan a directory and yield metadata as it's parsed.
        
        Args:
            directory: Path to directory to scan
            recursive: Whether to scan subdirectories
            
        Yields:
            ImageMetadata objects as they're parsed
        """
        image_files = self._collect_image_files(directory, recursive)
        total = len(image_files)
        completed = 0
        
        for path in image_files:
            try:
                metadata = self.parser.parse_image(str(path))
                yield metadata
            except Exception as e:
                print(f"Error parsing {path}: {e}")
            
            completed += 1
            if self.progress_callback:
                self.progress_callback(completed, total)
    
    def _collect_image_files(self, directory: str, recursive: bool) -> List[Path]:
        """
        Collect all image files in a directory.
        
        Args:
            directory: Path to directory
            recursive: Whether to scan subdirectories
            
        Returns:
            List of Path objects
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        image_files = []
        
        if recursive:
            for path in dir_path.rglob('*'):
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    image_files.append(path)
        else:
            for path in dir_path.iterdir():
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    image_files.append(path)
        
        # Sort for consistent ordering
        image_files.sort()
        
        return image_files
    
    def count_images(self, directory: str, recursive: bool = True) -> int:
        """
        Count the number of images in a directory without parsing.
        
        Args:
            directory: Path to directory
            recursive: Whether to scan subdirectories
            
        Returns:
            Number of image files
        """
        try:
            files = self._collect_image_files(directory, recursive)
            return len(files)
        except:
            return 0
