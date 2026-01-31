"""SQLite-based image index for fast filtering and retrieval."""
import sqlite3
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from ..models.image_data import ImageMetadata


class ImageIndex:
    """Manages a SQLite database index of image metadata."""
    
    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize the image index.
        
        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create the database tables."""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                modified_time REAL DEFAULT 0,
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
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for fast filtering
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_prompt ON images(prompt)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_negative_prompt ON images(negative_prompt)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_model ON images(model)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_source ON images(source)
        ''')
        
        self.conn.commit()
    
    def add_image(self, metadata: ImageMetadata) -> bool:
        """
        Add or update an image in the index.
        
        Args:
            metadata: ImageMetadata object to add
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        
        try:
            # Ensure all string fields are actually strings and handle special characters
            def safe_str(value):
                if value is None:
                    return ''
                if isinstance(value, (list, dict)):
                    return json.dumps(value)
                return str(value)
            
            def safe_int(value):
                """Safely convert value to int, handling lists and other types."""
                if value is None:
                    return 0
                if isinstance(value, (list, dict)):
                    return 0
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return 0
            
            def safe_float(value):
                """Safely convert value to float, handling lists and other types."""
                if value is None:
                    return 0.0
                if isinstance(value, (list, dict)):
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0
            
            cursor.execute('''
                INSERT OR REPLACE INTO images (
                    file_path, file_name, width, height, file_size, modified_time,
                    prompt, negative_prompt, model, model_hash, sampler, steps,
                    cfg_scale, seed, source, raw_metadata, extra_params, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                safe_str(metadata.file_path),
                safe_str(metadata.file_name),
                safe_int(metadata.width),
                safe_int(metadata.height),
                safe_int(metadata.file_size),
                safe_float(metadata.modified_time),
                safe_str(metadata.prompt),
                safe_str(metadata.negative_prompt),
                safe_str(metadata.model),
                safe_str(metadata.model_hash),
                safe_str(metadata.sampler),
                safe_int(metadata.steps),
                safe_float(metadata.cfg_scale),
                safe_int(metadata.seed),
                safe_str(metadata.source),
                safe_str(metadata.raw_metadata),
                json.dumps(metadata.extra_params) if metadata.extra_params else '{}'
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding image to index: {e}")
            return False
    
    def add_images(self, metadata_list: List[ImageMetadata]) -> int:
        """
        Add multiple images to the index.
        
        Args:
            metadata_list: List of ImageMetadata objects
            
        Returns:
            Number of images successfully added
        """
        count = 0
        for metadata in metadata_list:
            if self.add_image(metadata):
                count += 1
        return count
    
    def get_image(self, file_path: str) -> Optional[ImageMetadata]:
        """
        Get metadata for a specific image.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            ImageMetadata object or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM images WHERE file_path = ?', (file_path,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_metadata(row)
        return None
    
    def get_all_images(self) -> List[ImageMetadata]:
        """Get all images in the index."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM images ORDER BY file_path')
        return [self._row_to_metadata(row) for row in cursor.fetchall()]
    
    def filter_images(
        self,
        include_terms: List[str] = None,
        exclude_terms: List[str] = None,
        model: str = None,
        source: str = None,
        sort_by: str = 'path',
        reverse: bool = False
    ) -> List[ImageMetadata]:
        """
        Filter images based on criteria.
        
        Args:
            include_terms: Terms that must be in prompt (case-insensitive)
            exclude_terms: Terms that must NOT be in prompt (case-insensitive)
            model: Filter by model name (partial match)
            source: Filter by source (a1111, comfyui, unknown)
            sort_by: Sort field - 'path', 'date', 'dimensions', 'file_size', 'random'
            reverse: Reverse sort order
            
        Returns:
            List of matching ImageMetadata objects
        """
        cursor = self.conn.cursor()
        
        query = 'SELECT * FROM images WHERE 1=1'
        params = []
        
        # Include terms - all must match
        if include_terms:
            for term in include_terms:
                query += ' AND LOWER(prompt) LIKE ?'
                params.append(f'%{term.lower()}%')
        
        # Exclude terms - none must match
        if exclude_terms:
            for term in exclude_terms:
                query += ' AND LOWER(prompt) NOT LIKE ?'
                params.append(f'%{term.lower()}%')
        
        # Model filter
        if model:
            query += ' AND LOWER(model) LIKE ?'
            params.append(f'%{model.lower()}%')
        
        # Source filter
        if source:
            query += ' AND source = ?'
            params.append(source)
        
        # Apply sorting
        # For date, default is newest first (DESC), reverse is oldest first (ASC)
        # For other fields, default is ASC, reverse is DESC
        if sort_by == 'date':
            order_direction = 'ASC' if reverse else 'DESC'
            query += f' ORDER BY modified_time {order_direction}'
        elif sort_by == 'dimensions':
            # Sort by total pixels (width * height)
            order_direction = 'DESC' if reverse else 'ASC'
            query += f' ORDER BY (width * height) {order_direction}'
        elif sort_by == 'file_size':
            order_direction = 'DESC' if reverse else 'ASC'
            query += f' ORDER BY file_size {order_direction}'
        elif sort_by == 'random':
            query += ' ORDER BY RANDOM()'
        else:  # path (default)
            order_direction = 'DESC' if reverse else 'ASC'
            query += f' ORDER BY file_path {order_direction}'
        
        cursor.execute(query, params)
        return [self._row_to_metadata(row) for row in cursor.fetchall()]
    
    def remove_image(self, file_path: str) -> bool:
        """
        Remove an image from the index.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            True if removed, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM images WHERE file_path = ?', (file_path,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def clear(self) -> None:
        """Remove all images from the index."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM images')
        self.conn.commit()
    
    def get_stats(self) -> dict:
        """Get statistics about the index."""
        cursor = self.conn.cursor()
        
        # Total count
        cursor.execute('SELECT COUNT(*) FROM images')
        total = cursor.fetchone()[0]
        
        # Count by source
        cursor.execute('SELECT source, COUNT(*) FROM images GROUP BY source')
        by_source = {row[0] or 'unknown': row[1] for row in cursor.fetchall()}
        
        # Count with prompts
        cursor.execute('SELECT COUNT(*) FROM images WHERE prompt != ""')
        with_prompt = cursor.fetchone()[0]
        
        return {
            'total_images': total,
            'by_source': by_source,
            'with_prompt': with_prompt,
            'without_prompt': total - with_prompt
        }
    
    def _row_to_metadata(self, row: sqlite3.Row) -> ImageMetadata:
        """Convert a database row to ImageMetadata."""
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
            file_path=row['file_path'],
            file_name=row['file_name'],
            width=row['width'],
            height=row['height'],
            file_size=row['file_size'],
            modified_time=row['modified_time'],
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
    
    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
