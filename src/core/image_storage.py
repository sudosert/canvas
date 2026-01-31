"""Full image storage system with SQLite BLOB storage."""
import sqlite3
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import hashlib

from ..models.image_data import ImageMetadata


class ImageStorage:
    """
    Manages full image storage in SQLite database.
    Stores both metadata and image file data as BLOBs.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize image storage.
        
        Args:
            db_path: Path to SQLite database. Defaults to ~/.cache/sd-image-viewer/image_storage.db
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.cache/sd-image-viewer/image_storage.db")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create the database tables."""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stored_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                prompt TEXT DEFAULT '',
                negative_prompt TEXT DEFAULT '',
                model TEXT DEFAULT '',
                model_hash TEXT DEFAULT '',
                sampler TEXT DEFAULT '',
                steps INTEGER DEFAULT 0,
                cfg_scale REAL DEFAULT 0,
                seed INTEGER DEFAULT 0,
                source TEXT DEFAULT '',
                raw_metadata TEXT DEFAULT '',
                extra_params TEXT DEFAULT '{}',
                image_data BLOB NOT NULL,
                stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_deleted BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_stored_prompt ON stored_images(prompt)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_stored_file_hash ON stored_images(file_hash)
        ''')
        
        self.conn.commit()
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def store_image(self, metadata: ImageMetadata, image_data: bytes, 
                    delete_original: bool = False) -> bool:
        """
        Store an image in the database.
        
        Args:
            metadata: ImageMetadata object
            image_data: Raw image bytes
            delete_original: If True, delete the original file after storing
            
        Returns:
            True if stored successfully
        """
        cursor = self.conn.cursor()
        
        try:
            file_hash = self._compute_file_hash(metadata.file_path)
            
            cursor.execute('''
                INSERT OR REPLACE INTO stored_images (
                    original_path, file_name, file_hash, file_size, width, height,
                    prompt, negative_prompt, model, model_hash, sampler, steps,
                    cfg_scale, seed, source, raw_metadata, extra_params, image_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metadata.file_path,
                metadata.file_name,
                file_hash,
                metadata.file_size,
                metadata.width,
                metadata.height,
                metadata.prompt,
                metadata.negative_prompt,
                metadata.model,
                metadata.model_hash,
                metadata.sampler,
                metadata.steps,
                metadata.cfg_scale,
                metadata.seed,
                metadata.source,
                metadata.raw_metadata,
                str(metadata.extra_params),
                image_data
            ))
            
            self.conn.commit()
            
            # Delete original if requested
            if delete_original and os.path.exists(metadata.file_path):
                os.remove(metadata.file_path)
                cursor.execute('''
                    UPDATE stored_images SET original_deleted = 1 
                    WHERE original_path = ?
                ''', (metadata.file_path,))
                self.conn.commit()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to store image: {e}")
            return False
    
    def store_image_from_file(self, file_path: str, metadata: ImageMetadata = None,
                              delete_original: bool = False) -> bool:
        """
        Store an image from file path.
        
        Args:
            file_path: Path to image file
            metadata: Optional pre-parsed metadata
            delete_original: If True, delete the original file after storing
            
        Returns:
            True if stored successfully
        """
        try:
            # Read image data
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Parse metadata if not provided
            if metadata is None:
                from .metadata_parser import MetadataParser
                metadata = MetadataParser.parse_image(file_path)
            
            return self.store_image(metadata, image_data, delete_original)
            
        except Exception as e:
            print(f"[ERROR] Failed to store image from file: {e}")
            return False
    
    def get_image_data(self, original_path: str) -> Optional[bytes]:
        """
        Get image data by original path.
        
        Args:
            original_path: Original file path
            
        Returns:
            Image bytes or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT image_data FROM stored_images WHERE original_path = ?',
            (original_path,)
        )
        row = cursor.fetchone()
        
        if row:
            return row['image_data']
        return None
    
    def get_image_by_hash(self, file_hash: str) -> Optional[Tuple[ImageMetadata, bytes]]:
        """
        Get image by file hash.
        
        Args:
            file_hash: SHA256 hash of file content
            
        Returns:
            Tuple of (metadata, image_data) or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM stored_images WHERE file_hash = ?',
            (file_hash,)
        )
        row = cursor.fetchone()
        
        if row:
            metadata = self._row_to_metadata(row)
            return metadata, row['image_data']
        return None
    
    def get_all_metadata(self) -> List[ImageMetadata]:
        """Get metadata for all stored images."""
        print("[DEBUG] ImageStorage.get_all_metadata() called")
        try:
            cursor = self.conn.cursor()
            # Don't fetch image_data as it can be very large
            cursor.execute('''
                SELECT id, original_path, file_name, file_hash, file_size,
                       width, height, prompt, negative_prompt, model, model_hash,
                       sampler, steps, cfg_scale, seed, source, raw_metadata,
                       extra_params, stored_at, original_deleted
                FROM stored_images ORDER BY stored_at DESC
            ''')
            rows = cursor.fetchall()
            print(f"[DEBUG] Query returned {len(rows)} rows")
            result = [self._row_to_metadata(row) for row in rows]
            print(f"[DEBUG] get_all_metadata() returned {len(result)} images")
            return result
        except Exception as e:
            print(f"[ERROR] get_all_metadata() failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_image_details(self, original_path: str) -> Optional[Dict[str, Any]]:
        """
        Get additional details for a stored image.

        Args:
            original_path: Original file path of the image

        Returns:
            Dictionary with stored_at, original_deleted, file_size or None if not found
        """
        print(f"[DEBUG] get_image_details() called for: {original_path}")
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT stored_at, original_deleted, file_size FROM stored_images WHERE original_path = ?',
                (original_path,)
            )
            row = cursor.fetchone()
            if row:
                result = {
                    'stored_at': row['stored_at'],
                    'original_deleted': row['original_deleted'],
                    'file_size': row['file_size']
                }
                print(f"[DEBUG] get_image_details() found: {result}")
                return result
            print("[DEBUG] get_image_details() - no row found")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to get image details: {e}")
            return None

    def delete_image(self, original_path: str, delete_data: bool = True) -> bool:
        """
        Delete an image from storage.
        
        Args:
            original_path: Original file path
            delete_data: If True, delete the image data. If False, just mark as deleted.
            
        Returns:
            True if deleted successfully
        """
        cursor = self.conn.cursor()
        
        try:
            if delete_data:
                cursor.execute(
                    'DELETE FROM stored_images WHERE original_path = ?',
                    (original_path,)
                )
            else:
                cursor.execute('''
                    UPDATE stored_images SET original_deleted = 1 
                    WHERE original_path = ?
                ''', (original_path,))
            
            self.conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"[ERROR] Failed to delete image: {e}")
            return False
    
    def export_image(self, original_path: str, destination: str) -> bool:
        """
        Export an image from storage to a file.
        
        Args:
            original_path: Original file path (key in database)
            destination: Destination file path
            
        Returns:
            True if exported successfully
        """
        image_data = self.get_image_data(original_path)
        
        if image_data is None:
            return False
        
        try:
            with open(destination, 'wb') as f:
                f.write(image_data)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to export image: {e}")
            return False
    
    def cleanup_deleted_originals(self, dry_run: bool = True) -> List[str]:
        """
        Find and optionally remove entries where original file no longer exists.
        
        Args:
            dry_run: If True, only report what would be deleted
            
        Returns:
            List of paths that were/would be cleaned up
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT original_path FROM stored_images')
        
        to_cleanup = []
        for row in cursor.fetchall():
            path = row['original_path']
            if not os.path.exists(path):
                to_cleanup.append(path)
        
        if not dry_run:
            for path in to_cleanup:
                self.delete_image(path, delete_data=True)
        
        return to_cleanup
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        cursor = self.conn.cursor()
        
        # Total count and size
        cursor.execute('''
            SELECT COUNT(*), SUM(file_size), SUM(LENGTH(image_data)) 
            FROM stored_images
        ''')
        row = cursor.fetchone()
        total_count = row[0] or 0
        total_original_size = row[1] or 0
        total_storage_size = row[2] or 0
        
        # Count of deleted originals
        cursor.execute('''
            SELECT COUNT(*) FROM stored_images WHERE original_deleted = 1
        ''')
        deleted_count = cursor.fetchone()[0] or 0
        
        # Database file size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        
        return {
            'total_images': total_count,
            'deleted_originals': deleted_count,
            'original_size_mb': total_original_size / (1024 * 1024),
            'storage_size_mb': total_storage_size / (1024 * 1024),
            'database_size_mb': db_size / (1024 * 1024)
        }
    
    def _row_to_metadata(self, row: sqlite3.Row) -> ImageMetadata:
        """Convert database row to ImageMetadata."""
        import json
        import ast
        
        extra_params_raw = row['extra_params'] or '{}'
        try:
            extra_params = json.loads(extra_params_raw)
        except json.JSONDecodeError:
            # Try parsing as Python literal (handles single-quoted strings)
            try:
                extra_params = ast.literal_eval(extra_params_raw)
            except (ValueError, SyntaxError):
                extra_params = {}
        
        return ImageMetadata(
            file_path=row['original_path'],
            file_name=row['file_name'],
            width=row['width'],
            height=row['height'],
            file_size=row['file_size'],
            modified_time=0,  # Not applicable for stored images
            prompt=row['prompt'] or '',
            negative_prompt=row['negative_prompt'] or '',
            model=row['model'] or '',
            model_hash=row['model_hash'] or '',
            sampler=row['sampler'] or '',
            steps=row['steps'],
            cfg_scale=row['cfg_scale'],
            seed=row['seed'],
            source=row['source'] or '',
            raw_metadata=row['raw_metadata'] or '',
            extra_params=extra_params
        )
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
