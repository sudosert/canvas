# Database Recommendations for Large Image Collections

## Current Architecture Analysis

### SQLite BLOB Storage Limitations
- **File size limit**: 2TB (with default settings), but practical limit much lower
- **Performance**: Degrades significantly with large BLOBs (>1MB each)
- **Memory usage**: Entire BLOB loaded into memory on read
- **Concurrency**: Limited write concurrency (file-level locking)
- **Backup/restore**: Single large file is hard to manage

### Expected Scale
- 10,000 images × 5MB average = 50GB database
- 100,000 images × 5MB average = 500GB database

## Recommended Solutions

### Option 1: Hybrid Approach (Recommended)
Keep metadata in SQLite, store image data on filesystem with content-addressable storage.

**Structure:**
```
~/.cache/sd-image-viewer/
├── metadata.db           # SQLite: metadata, tags, file hashes
└── images/               # Filesystem: actual image data
    ├── ab/
    │   └── cd1234...     # Content-addressable storage
    ├── ef/
    │   └── 567890...
    └── ...
```

**Pros:**
- Metadata queries remain fast
- Image data can be memory-mapped for efficient access
- Easy backup/restore (just copy files)
- Deduplication by content hash
- No database bloat

**Cons:**
- Two storage systems to manage
- Slightly more complex implementation

### Option 2: PostgreSQL with Large Objects (LO)
Replace SQLite with PostgreSQL using its Large Object facility.

**Pros:**
- Handles large BLOBs efficiently
- Streaming access (no memory loading)
- Better concurrency
- Built-in backup tools
- Can run locally or remote

**Cons:**
- Requires PostgreSQL installation
- More complex setup
- Overkill for single-user app

### Option 3: LevelDB/RocksDB
Key-value store optimized for large values.

**Pros:**
- Designed for large values
- Fast sequential reads
- Compression support
- Single file (simpler than filesystem)

**Cons:**
- No SQL queries for metadata
- Would need two databases (metadata + images)
- Less familiar API

### Option 4: Keep Current SQLite but Optimize
Optimize the current SQLite implementation.

**Optimizations:**
1. **Chunked storage**: Split large images into chunks
2. **External files**: Store images as separate files, SQLite only tracks paths
3. **WAL mode**: Enable Write-Ahead Logging for better concurrency
4. **Memory mapping**: Use SQLite's mmap feature
5. **Page size tuning**: Increase page size for BLOB-heavy databases

## Recommended Implementation: Hybrid Approach

### Database Schema
```sql
-- metadata.db
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    original_path TEXT UNIQUE,
    file_name TEXT,
    content_hash TEXT UNIQUE,  -- SHA256 of image data
    file_size INTEGER,
    -- metadata fields...
    storage_path TEXT,         -- Relative path in images/
    storage_type TEXT DEFAULT 'file'  -- 'file' or 'db' for small images
);
```

### Filesystem Storage
```python
# Content-addressable storage
hash = sha256(image_data).hexdigest()
storage_path = f"images/{hash[:2]}/{hash[2:4]}/{hash}"
# e.g., images/ab/cd/abcdef123456...
```

### Benefits
1. **Automatic deduplication**: Same image stored once
2. **Immutable storage**: Never modify files, only add/delete
3. **Easy cleanup**: Just delete files not referenced in DB
4. **Fast access**: Direct file reads, no SQL overhead for image data
5. **Scalable**: Filesystem handles large files better than SQLite

### Migration Path
1. Add `storage_path` and `content_hash` columns
2. Move existing BLOBs to filesystem
3. Update code to read from filesystem
4. Vacuum database to reclaim space

## Performance Comparison

| Approach | 10K Images | 100K Images | 1M Images |
|----------|------------|-------------|-----------|
| SQLite BLOB | ⚠️ Slow | ❌ Unusable | ❌ Impossible |
| Hybrid | ✅ Fast | ✅ Fast | ✅ Good |
| PostgreSQL | ✅ Fast | ✅ Fast | ✅ Fast |
| LevelDB | ✅ Fast | ✅ Fast | ⚠️ Moderate |

## Conclusion

For this application, the **hybrid approach** offers the best balance of:
- Simplicity (no external dependencies)
- Performance (filesystem for images, SQLite for metadata)
- Scalability (tested to millions of files)
- Maintainability (standard tools work)

If you need to support 100K+ images, implement the hybrid storage approach.