"""Dialog for managing image storage."""
import os
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QGroupBox, QSpinBox, QFileDialog,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont

from ..core.image_storage import ImageStorage
from ..core.postgres_image_storage import PostgresImageStorage, POSTGRES_AVAILABLE
from ..core.image_scanner import ImageScanner
from ..core.metadata_parser import MetadataParser
from ..models.image_data import ImageMetadata


class ImageStorageDialog(QDialog):
    """Dialog for managing image storage and cleanup."""

    def __init__(self, parent=None, skip_update: bool = False):
        super().__init__(parent)
        print("[DEBUG] ImageStorageDialog.__init__ starting...")
        self.setWindowTitle("Image Storage Manager")
        self.setMinimumSize(800, 600)
        
        # Store configuration
        self.skip_update = skip_update
        
        # Load settings
        self.settings = QSettings("SDImageViewer", "Settings")
        
        # Initialize storage backends
        print("[DEBUG] Creating ImageStorage instance...")
        self.storage = ImageStorage()
        print("[DEBUG] ImageStorage created successfully")
        
        # Initialize PostgreSQL storage if configured
        self.postgres_storage = None
        self._init_postgres_storage()

        print("[DEBUG] Setting up UI...")
        self._setup_ui()
        print("[DEBUG] UI setup complete")

        print("[DEBUG] Refreshing stats...")
        self._refresh_stats()
        print("[DEBUG] Stats refresh complete")
    
    def _build_postgres_connection_string(self) -> str:
        """Build PostgreSQL connection string from settings and env vars."""
        host = self.settings.value("postgres_host", "") or os.environ.get("POSTGRES_IP", "")
        port = self.settings.value("postgres_port", "5432")
        database = self.settings.value("postgres_db", "sd_images")
        user = self.settings.value("postgres_user", "") or os.environ.get("POSTGRES_USER", "")
        password = os.environ.get("POSTGRES_PASS", "")
        
        if not all([host, user, password]):
            return ""
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    def _init_postgres_storage(self):
        """Initialize PostgreSQL storage if enabled in settings."""
        postgres_enabled = self.settings.value("postgres_enabled", False)
        if isinstance(postgres_enabled, str):
            postgres_enabled = postgres_enabled.lower() == "true"
        
        if postgres_enabled and POSTGRES_AVAILABLE:
            conn_string = self._build_postgres_connection_string()
            if conn_string:
                try:
                    self.postgres_storage = PostgresImageStorage(conn_string)
                    print(f"[DEBUG] PostgreSQL storage initialized: {self.postgres_storage.is_connected()}")
                except Exception as e:
                    print(f"[ERROR] Failed to initialize PostgreSQL storage: {e}")
                    self.postgres_storage = None
    
    def _get_active_storage(self):
        """Get the currently active storage backend."""
        storage_type = self.storage_combo.currentData()
        if storage_type == "postgres" and self.postgres_storage:
            return self.postgres_storage
        return self.storage
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Storage backend selector
        backend_group = QGroupBox("Storage Backend")
        backend_layout = QHBoxLayout(backend_group)
        
        backend_layout.addWidget(QLabel("Storage Type:"))
        self.storage_combo = QComboBox()
        self.storage_combo.addItem("📁 Local SQLite", "sqlite")
        
        # Add PostgreSQL option if available
        if POSTGRES_AVAILABLE:
            self.storage_combo.addItem("🐘 PostgreSQL", "postgres")
            if self.postgres_storage and self.postgres_storage.is_connected():
                self.storage_combo.setCurrentIndex(1)
        else:
            self.storage_combo.addItem("🐘 PostgreSQL (not installed)", "postgres_unavailable")
            self.storage_combo.setItemData(1, False, Qt.ItemDataRole.UserRole - 1)
        
        self.storage_combo.currentIndexChanged.connect(self._on_storage_changed)
        backend_layout.addWidget(self.storage_combo)
        
        # Connection status
        self.backend_status = QLabel()
        self._update_backend_status()
        backend_layout.addWidget(self.backend_status)
        
        backend_layout.addStretch()
        layout.addWidget(backend_group)
        
        # Stats group
        stats_group = QGroupBox("Storage Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Loading...")
        self.stats_label.setFont(QFont("Monospace", 10))
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # Import section
        import_group = QGroupBox("Import Images")
        import_layout = QVBoxLayout(import_group)
        
        import_info = QLabel("Import images from a folder into the database. "
                            "Optionally delete originals after import.")
        import_info.setWordWrap(True)
        import_layout.addWidget(import_info)
        
        import_btn_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("Import Folder...")
        self.import_btn.clicked.connect(self._import_folder)
        import_btn_layout.addWidget(self.import_btn)
        
        self.delete_after_import = QCheckBox("Delete original files after import")
        self.delete_after_import.setChecked(False)
        import_btn_layout.addWidget(self.delete_after_import)
        
        import_btn_layout.addStretch()
        import_layout.addLayout(import_btn_layout)
        
        layout.addWidget(import_group)
        
        # Cleanup section
        cleanup_group = QGroupBox("Cleanup")
        cleanup_layout = QVBoxLayout(cleanup_group)
        
        cleanup_info = QLabel("Remove entries for images where the original file no longer exists.")
        cleanup_info.setWordWrap(True)
        cleanup_layout.addWidget(cleanup_info)
        
        cleanup_btn_layout = QHBoxLayout()
        
        self.scan_cleanup_btn = QPushButton("Scan for Orphaned Entries")
        self.scan_cleanup_btn.clicked.connect(self._scan_for_cleanup)
        cleanup_btn_layout.addWidget(self.scan_cleanup_btn)
        
        self.cleanup_btn = QPushButton("Clean Up Orphaned Entries")
        self.cleanup_btn.clicked.connect(self._cleanup_orphaned)
        self.cleanup_btn.setEnabled(False)
        cleanup_btn_layout.addWidget(self.cleanup_btn)
        
        cleanup_btn_layout.addStretch()
        cleanup_layout.addLayout(cleanup_btn_layout)
        
        self.cleanup_results = QLabel("")
        cleanup_layout.addWidget(self.cleanup_results)
        
        layout.addWidget(cleanup_group)
        
        # Stored images table
        table_group = QGroupBox("Stored Images")
        table_layout = QVBoxLayout(table_group)
        
        self.images_table = QTableWidget()
        self.images_table.setColumnCount(5)
        self.images_table.setHorizontalHeaderLabels([
            "File Name", "Dimensions", "Size", "Stored At", "Original Deleted"
        ])
        self.images_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.images_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.images_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.images_table)
        
        # Table buttons
        table_btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self._refresh_image_list)
        table_btn_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("Export Selected...")
        self.export_btn.clicked.connect(self._export_selected)
        table_btn_layout.addWidget(self.export_btn)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)
        table_btn_layout.addWidget(self.delete_btn)
        
        table_btn_layout.addStretch()
        table_layout.addLayout(table_btn_layout)
        
        layout.addWidget(table_group, 1)  # Give table stretch priority
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: #252525;
            }
            QGroupBox {
                color: #eee;
                border: 1px solid #444;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #eee;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QTableWidget {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                gridline-color: #444;
            }
            QTableWidget::item:selected {
                background-color: #4a9eff;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #eee;
                padding: 5px;
                border: 1px solid #444;
            }
            QCheckBox {
                color: #eee;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        # Initial load
        self._refresh_image_list()
    
    def _on_storage_changed(self, index):
        """Handle storage backend change."""
        self._update_backend_status()
        self._refresh_stats()
        self._refresh_image_list()
    
    def _update_backend_status(self):
        """Update the backend status label."""
        storage_type = self.storage_combo.currentData()
        
        if storage_type == "postgres":
            if self.postgres_storage and self.postgres_storage.is_connected():
                self.backend_status.setText("✅ Connected")
                self.backend_status.setStyleSheet("color: #4caf50;")
            else:
                self.backend_status.setText("❌ Not connected")
                self.backend_status.setStyleSheet("color: #ff6b6b;")
        else:
            self.backend_status.setText("✅ Ready")
            self.backend_status.setStyleSheet("color: #4caf50;")
    
    def _refresh_stats(self):
        """Refresh storage statistics display."""
        storage = self._get_active_storage()
        
        if isinstance(storage, PostgresImageStorage):
            stats = storage.get_storage_stats()
            if stats.get('connected'):
                stats_text = f"""
<b>Backend:</b> PostgreSQL
<b>Connected:</b> Yes
<b>Total Images:</b> {stats.get('total_images', 0)}
<b>Total Size:</b> {stats.get('total_size_mb', 0):.2f} MB
<b>Database Size:</b> {stats.get('database_size', 'Unknown')}
                """.strip()
            else:
                stats_text = "<b>Backend:</b> PostgreSQL<br><b>Status:</b> Not connected"
        else:
            stats = self.storage.get_storage_stats()
            stats_text = f"""
<b>Backend:</b> Local SQLite
<b>Total Images:</b> {stats['total_images']}
<b>Deleted Originals:</b> {stats['deleted_originals']}
<b>Original Size:</b> {stats['original_size_mb']:.2f} MB
<b>Storage Size:</b> {stats['storage_size_mb']:.2f} MB
<b>Database File:</b> {stats['database_size_mb']:.2f} MB
            """.strip()
        
        self.stats_label.setText(stats_text)
    
    def _refresh_image_list(self):
        """Refresh the list of stored images."""
        print("[DEBUG] _refresh_image_list() starting...")
        
        # Skip if database updates are disabled
        if self.skip_update:
            print("[DEBUG] Skipping image list refresh (--skip-db-update is set)")
            self.images_table.setRowCount(0)
            self.stats_label.setText("<i>Database updates disabled (using --skip-db-update)</i>")
            return
        
        self.images_table.setRowCount(0)
        print("[DEBUG] Table cleared")
        
        storage = self._get_active_storage()
        
        # Check if using PostgreSQL and not connected
        if isinstance(storage, PostgresImageStorage) and not storage.is_connected():
            self.stats_label.setText("<b>Backend:</b> PostgreSQL<br><b>Status:</b> Not connected")
            return

        print("[DEBUG] Calling get_all_metadata()...")
        metadata_list = storage.get_all_metadata()
        print(f"[DEBUG] Got {len(metadata_list)} metadata entries")

        for i, metadata in enumerate(metadata_list):
            print(f"[DEBUG] Processing image {i+1}/{len(metadata_list)}: {metadata.file_name}")
            row = self.images_table.rowCount()
            self.images_table.insertRow(row)

            self.images_table.setItem(row, 0, QTableWidgetItem(metadata.file_name))
            self.images_table.setItem(row, 1, QTableWidgetItem(metadata.dimensions))

            size_mb = metadata.file_size / (1024 * 1024)
            self.images_table.setItem(row, 2, QTableWidgetItem(f"{size_mb:.2f} MB"))

            # For PostgreSQL, we don't have stored_at in metadata, so show N/A
            stored_at = "N/A" if isinstance(storage, PostgresImageStorage) else "Unknown"
            self.images_table.setItem(row, 3, QTableWidgetItem(str(stored_at)))

            # For PostgreSQL, we don't track original_deleted
            deleted = "N/A" if isinstance(storage, PostgresImageStorage) else "No"
            self.images_table.setItem(row, 4, QTableWidgetItem(deleted))

            # Store path in item data for later use
            self.images_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, metadata.file_path)

        print("[DEBUG] Calling _refresh_stats()...")
        self._refresh_stats()
        print("[DEBUG] _refresh_image_list() complete")
    
    def _import_folder(self):
        """Import images from a folder."""
        # Skip if database updates are disabled
        if self.skip_update:
            QMessageBox.information(
                self,
                "Import Disabled",
                "Import is disabled when using --skip-db-update flag."
            )
            return
        
        storage = self._get_active_storage()
        
        # Check if using PostgreSQL and not connected
        if isinstance(storage, PostgresImageStorage) and not storage.is_connected():
            QMessageBox.warning(
                self,
                "Not Connected",
                "PostgreSQL is not connected. Please check your settings."
            )
            return
        
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Import")
        if not folder:
            return
        
        # Count images
        scanner = ImageScanner()
        count = scanner.count_images(folder)
        
        if count == 0:
            QMessageBox.information(self, "No Images", "No images found in selected folder.")
            return
        
        delete_originals = self.delete_after_import.isChecked()
        action = "importing and deleting" if delete_originals else "importing"
        
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            f"Found {count} images. Proceed with {action}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Show progress
        progress = QProgressDialog("Importing images...", "Cancel", 0, count, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        
        imported = 0
        failed = 0
        
        try:
            def progress_callback(current, total):
                progress.setValue(current)
                return not progress.wasCanceled()
            
            scanner = ImageScanner(progress_callback=progress_callback)
            images = scanner.scan_directory(folder)
            
            for i, metadata in enumerate(images):
                if progress.wasCanceled():
                    break
                
                progress.setLabelText(f"Importing {metadata.file_name}...")
                
                if isinstance(storage, PostgresImageStorage):
                    # Use PostgreSQL storage
                    result = storage.store_image_from_file(metadata.file_path, metadata)
                    if result:
                        imported += 1
                    else:
                        failed += 1
                    # Note: PostgreSQL storage doesn't support delete_original in the same way
                    if delete_originals and result:
                        try:
                            os.remove(metadata.file_path)
                        except Exception as e:
                            print(f"[WARNING] Failed to delete original: {e}")
                else:
                    # Use SQLite storage
                    if storage.store_image_from_file(
                        metadata.file_path, 
                        metadata,
                        delete_original=delete_originals
                    ):
                        imported += 1
                    else:
                        failed += 1
                
                progress.setValue(i + 1)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {str(e)}")
        
        progress.close()
        
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported: {imported}\nFailed: {failed}"
        )
        
        self._refresh_image_list()
    
    def _scan_for_cleanup(self):
        """Scan for orphaned entries."""
        # Skip if database updates are disabled
        if self.skip_update:
            self.cleanup_results.setText("<i>Cleanup disabled (using --skip-db-update)</i>")
            self.cleanup_btn.setEnabled(False)
            return
        
        storage = self._get_active_storage()
        
        # Cleanup not supported for PostgreSQL
        if isinstance(storage, PostgresImageStorage):
            self.cleanup_results.setText("<i>Cleanup not available for PostgreSQL backend</i>")
            self.cleanup_btn.setEnabled(False)
            return
        
        orphaned = storage.cleanup_deleted_originals(dry_run=True)
        
        if orphaned:
            self.cleanup_results.setText(f"Found {len(orphaned)} orphaned entries")
            self.cleanup_btn.setEnabled(True)
        else:
            self.cleanup_results.setText("No orphaned entries found")
            self.cleanup_btn.setEnabled(False)
    
    def _cleanup_orphaned(self):
        """Clean up orphaned entries."""
        storage = self._get_active_storage()
        
        # Cleanup not supported for PostgreSQL
        if isinstance(storage, PostgresImageStorage):
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This will permanently delete database entries for images where the original file no longer exists.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            orphaned = storage.cleanup_deleted_originals(dry_run=False)
            QMessageBox.information(self, "Cleanup Complete", f"Removed {len(orphaned)} entries")
            self.cleanup_results.setText("")
            self.cleanup_btn.setEnabled(False)
            self._refresh_image_list()
    
    def _export_selected(self):
        """Export selected images to files."""
        selected_rows = self.images_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select images to export")
            return
        
        storage = self._get_active_storage()
        
        # Get unique rows
        rows = set(index.row() for index in selected_rows)
        
        # Select destination folder
        dest_folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not dest_folder:
            return
        
        exported = 0
        failed = 0
        
        for row in rows:
            path_item = self.images_table.item(row, 0)
            original_path = path_item.data(Qt.ItemDataRole.UserRole)
            file_name = path_item.text()
            
            dest_path = f"{dest_folder}/{file_name}"
            
            if isinstance(storage, PostgresImageStorage):
                # For PostgreSQL, we need to get image by path
                # First get the metadata to find the ID
                metadata_list = storage.get_all_metadata()
                image_id = None
                for meta in metadata_list:
                    if meta.file_path == original_path:
                        # Get ID from database - need to query by path
                        import psycopg2
                        from psycopg2.extras import RealDictCursor
                        try:
                            with storage.conn.cursor(cursor_factory=RealDictCursor) as cur:
                                cur.execute(
                                    "SELECT id FROM stored_images WHERE original_path = %s",
                                    (original_path,)
                                )
                                result = cur.fetchone()
                                if result:
                                    image_id = result['id']
                        except Exception as e:
                            print(f"[ERROR] Failed to get image ID: {e}")
                        break
                
                if image_id and storage.export_image(image_id, dest_path):
                    exported += 1
                else:
                    failed += 1
            else:
                if storage.export_image(original_path, dest_path):
                    exported += 1
                else:
                    failed += 1
        
        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported: {exported}\nFailed: {failed}"
        )
    
    def _delete_selected(self):
        """Delete selected images from storage."""
        # Skip if database updates are disabled
        if self.skip_update:
            QMessageBox.information(
                self,
                "Delete Disabled",
                "Delete is disabled when using --skip-db-update flag."
            )
            return
        
        storage = self._get_active_storage()
        
        selected_rows = self.images_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select images to delete")
            return
        
        # Get unique rows
        rows = set(index.row() for index in selected_rows)
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Permanently delete {len(rows)} images from storage?\n\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for row in rows:
                path_item = self.images_table.item(row, 0)
                original_path = path_item.data(Qt.ItemDataRole.UserRole)
                
                if isinstance(storage, PostgresImageStorage):
                    # For PostgreSQL, need to find ID by path
                    try:
                        import psycopg2
                        from psycopg2.extras import RealDictCursor
                        with storage.conn.cursor(cursor_factory=RealDictCursor) as cur:
                            cur.execute(
                                "SELECT id FROM stored_images WHERE original_path = %s",
                                (original_path,)
                            )
                            result = cur.fetchone()
                            if result:
                                storage.delete_image(result['id'])
                    except Exception as e:
                        print(f"[ERROR] Failed to delete image: {e}")
                else:
                    storage.delete_image(original_path, delete_data=True)
            
            self._refresh_image_list()
