"""PostgreSQL-backed image storage for large collections."""
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import hashlib
import io

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from ..models.image_data import ImageMetadata


class PostgresImageStorage:
    """
    Stores full image data in PostgreSQL Large Objects.
    Metadata is cached locally in SQLite for fast access.
    """
    
    def __init__(self, connection_string: str = None):
        """
        Initialize PostgreSQL storage.
        
        Args:
            connection_string: PostgreSQL connection string.
                             e.g., "postgresql://user:pass@localhost:5432/sd_images"
        """
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL storage. Install with: pip install psycopg2-binary")
        
        self.connection_string = connection_string
        self.conn = None
        
        if connection_string:
            self._connect()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self._create_tables()
        except Exception as e:
            print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
            self.conn = None
    
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        if self.conn is None:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except:
            return False
    
    def _create_tables(self):
        """Create necessary tables."""
        with self.conn.cursor() as cur:
            # Main images table with Large Object reference
            cur.execute('''
                CREATE TABLE IF NOT EXISTS stored_images (
                    id SERIAL PRIMARY KEY,
                    original_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    content_hash TEXT UNIQUE NOT NULL,
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
                    extra_params JSONB DEFAULT '{}',
                    lo_oid OID,  -- Large Object OID
                    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_pg_prompt ON stored_images USING gin(to_tsvector('english', prompt))
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_pg_hash ON stored_images(content_hash)
            ''')
            
            self.conn.commit()
    
    def _compute_content_hash(self, image_data: bytes) -> str:
        """Compute SHA256 hash of image content."""
        return hashlib.sha256(image_data).hexdigest()
    
    def store_image(self, metadata: ImageMetadata, image_data: bytes) -> Optional[int]:
        """
        Store an image in PostgreSQL.
        
        Args:
            metadata: ImageMetadata object
            image_data: Raw image bytes
            
        Returns:
            Image ID if stored successfully, None otherwise
        """
        if not self.is_connected():
            print("[ERROR] Not connected to PostgreSQL")
            return None
        
        content_hash = self._compute_content_hash(image_data)
        
        # Check for duplicate
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM stored_images WHERE content_hash = %s",
                (content_hash,)
            )
            if cur.fetchone():
                print(f"[DEBUG] Image already exists (hash: {content_hash[:16]}...)")
                return None
        
        try:
            # Create Large Object
            lo_oid = self.conn.lo_create(0)
            lo = self.conn.lo_open(lo_oid, mode=psycopg2.extensions.LO_WRITE)
            
            try:
                # Write data in chunks to handle large files
                chunk_size = 1024 * 1024  # 1MB chunks
                for i in range(0, len(image_data), chunk_size):
                    chunk = image_data[i:i + chunk_size]
                    lo.write(chunk)
            finally:
                lo.close()
            
            # Insert metadata
            with self.conn.cursor() as cur:
                import json
                cur.execute('''
                    INSERT INTO stored_images (
                        original_path, file_name, content_hash, file_size, width, height,
                        prompt, negative_prompt, model, model_hash, sampler, steps,
                        cfg_scale, seed, source, raw_metadata, extra_params, lo_oid
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    metadata.file_path,
                    metadata.file_name,
                    content_hash,
                    len(image_data),
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
                    json.dumps(metadata.extra_params),
                    lo_oid
                ))
                
                result = cur.fetchone()
                self.conn.commit()
                
                print(f"[DEBUG] Stored image with ID {result[0]}, LO OID {lo_oid}")
                return result[0]
                
        except Exception as e:
            self.conn.rollback()
            print(f"[ERROR] Failed to store image: {e}")
            return None
    
    def store_image_from_file(self, file_path: str, metadata: ImageMetadata = None) -> Optional[int]:
        """Store an image from file path."""
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            if metadata is None:
                from .metadata_parser import MetadataParser
                metadata = MetadataParser.parse_image(file_path)
            
            return self.store_image(metadata, image_data)
            
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            return None
    
    def get_image_data(self, image_id: int) -> Optional[bytes]:
        """
        Get image data by ID.
        
        Args:
            image_id: Image ID in database
            
        Returns:
            Image bytes or None
        """
        if not self.is_connected():
            return None
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT lo_oid FROM stored_images WHERE id = %s",
                    (image_id,)
                )
                row = cur.fetchone()
                
                if not row or not row[0]:
                    return None
                
                lo_oid = row[0]
                lo = self.conn.lo_open(lo_oid, mode=psycopg2.extensions.LO_READ)
                
                try:
                    # Read in chunks
                    chunks = []
                    while True:
                        chunk = lo.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        chunks.append(chunk)
                    return b''.join(chunks)
                finally:
                    lo.close()
                
        except Exception as e:
            print(f"[ERROR] Failed to read image: {e}")
            return None
    
    def get_image_data_by_hash(self, content_hash: str) -> Optional[bytes]:
        """Get image data by content hash."""
        if not self.is_connected():
            return None
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM stored_images WHERE content_hash = %s",
                    (content_hash,)
                )
                row = cur.fetchone()
                
                if row:
                    return self.get_image_data(row[0])
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to find image: {e}")
            return None
    
    def get_metadata(self, image_id: int) -> Optional[ImageMetadata]:
        """Get metadata by image ID."""
        if not self.is_connected():
            return None
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM stored_images WHERE id = %s",
                    (image_id,)
                )
                row = cur.fetchone()
                
                if row:
                    return self._row_to_metadata(row)
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to get metadata: {e}")
            return None
    
    def get_all_metadata(self) -> List[ImageMetadata]:
        """Get metadata for all stored images."""
        if not self.is_connected():
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM stored_images ORDER BY stored_at DESC")
                return [self._row_to_metadata(row) for row in cur.fetchall()]
                
        except Exception as e:
            print(f"[ERROR] Failed to list images: {e}")
            return []
    
    def delete_image(self, image_id: int) -> bool:
        """
        Delete an image from storage.
        
        Args:
            image_id: Image ID to delete
            
        Returns:
            True if deleted
        """
        if not self.is_connected():
            return False
        
        try:
            with self.conn.cursor() as cur:
                # Get Large Object OID
                cur.execute(
                    "SELECT lo_oid FROM stored_images WHERE id = %s",
                    (image_id,)
                )
                row = cur.fetchone()
                
                if row and row[0]:
                    # Unlink Large Object
                    self.conn.lo_unlink(row[0])
                
                # Delete record
                cur.execute(
                    "DELETE FROM stored_images WHERE id = %s",
                    (image_id,)
                )
                
                self.conn.commit()
                return cur.rowcount > 0
                
        except Exception as e:
            self.conn.rollback()
            print(f"[ERROR] Failed to delete image: {e}")
            return False
    
    def export_image(self, image_id: int, destination: str) -> bool:
        """Export image to file."""
        image_data = self.get_image_data(image_id)
        
        if image_data is None:
            return False
        
        try:
            with open(destination, 'wb') as f:
                f.write(image_data)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to export: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        if not self.is_connected():
            return {'connected': False}
        
        try:
            with self.conn.cursor() as cur:
                # Count and total size
                cur.execute('''
                    SELECT COUNT(*), SUM(file_size) 
                    FROM stored_images
                ''')
                count, total_size = cur.fetchone()
                
                # Database size
                cur.execute('''
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                ''')
                db_size = cur.fetchone()[0]
                
                return {
                    'connected': True,
                    'total_images': count or 0,
                    'total_size_mb': (total_size or 0) / (1024 * 1024),
                    'database_size': db_size
                }
                
        except Exception as e:
            print(f"[ERROR] Failed to get stats: {e}")
            return {'connected': True, 'error': str(e)}
    
    def _row_to_metadata(self, row: Dict) -> ImageMetadata:
        """Convert database row to ImageMetadata."""
        import json
        return ImageMetadata(
            file_path=row['original_path'],
            file_name=row['file_name'],
            width=row['width'],
            height=row['height'],
            file_size=row['file_size'],
            modified_time=0,
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
            extra_params=row.get('extra_params', {})
        )
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
