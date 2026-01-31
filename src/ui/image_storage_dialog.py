"""Dialog for managing image storage."""
from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QGroupBox, QSpinBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ..core.image_storage import ImageStorage
from ..core.image_scanner import ImageScanner
from ..core.metadata_parser import MetadataParser
from ..models.image_data import ImageMetadata


class ImageStorageDialog(QDialog):
    """Dialog for managing image storage and cleanup."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Storage Manager")
        self.setMinimumSize(800, 600)
        
        self.storage = ImageStorage()
        self._setup_ui()
        self._refresh_stats()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
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
    
    def _refresh_stats(self):
        """Refresh storage statistics display."""
        stats = self.storage.get_storage_stats()
        
        stats_text = f"""
<b>Total Images:</b> {stats['total_images']}
<b>Deleted Originals:</b> {stats['deleted_originals']}
<b>Original Size:</b> {stats['original_size_mb']:.2f} MB
<b>Storage Size:</b> {stats['storage_size_mb']:.2f} MB
<b>Database File:</b> {stats['database_size_mb']:.2f} MB
        """.strip()
        
        self.stats_label.setText(stats_text)
    
    def _refresh_image_list(self):
        """Refresh the list of stored images."""
        self.images_table.setRowCount(0)
        
        metadata_list = self.storage.get_all_metadata()
        
        for metadata in metadata_list:
            row = self.images_table.rowCount()
            self.images_table.insertRow(row)
            
            # Get additional info from storage
            cursor = self.storage.conn.cursor()
            cursor.execute('''
                SELECT stored_at, original_deleted, file_size 
                FROM stored_images WHERE original_path = ?
            ''', (metadata.file_path,))
            db_row = cursor.fetchone()
            
            self.images_table.setItem(row, 0, QTableWidgetItem(metadata.file_name))
            self.images_table.setItem(row, 1, QTableWidgetItem(metadata.dimensions))
            
            size_mb = (db_row['file_size'] if db_row else 0) / (1024 * 1024)
            self.images_table.setItem(row, 2, QTableWidgetItem(f"{size_mb:.2f} MB"))
            
            stored_at = db_row['stored_at'] if db_row else "Unknown"
            self.images_table.setItem(row, 3, QTableWidgetItem(str(stored_at)))
            
            deleted = "Yes" if (db_row and db_row['original_deleted']) else "No"
            self.images_table.setItem(row, 4, QTableWidgetItem(deleted))
            
            # Store path in item data for later use
            self.images_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, metadata.file_path)
        
        self._refresh_stats()
    
    def _import_folder(self):
        """Import images from a folder."""
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
                
                if self.storage.store_image_from_file(
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
        orphaned = self.storage.cleanup_deleted_originals(dry_run=True)
        
        if orphaned:
            self.cleanup_results.setText(f"Found {len(orphaned)} orphaned entries")
            self.cleanup_btn.setEnabled(True)
        else:
            self.cleanup_results.setText("No orphaned entries found")
            self.cleanup_btn.setEnabled(False)
    
    def _cleanup_orphaned(self):
        """Clean up orphaned entries."""
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This will permanently delete database entries for images where the original file no longer exists.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            orphaned = self.storage.cleanup_deleted_originals(dry_run=False)
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
            
            if self.storage.export_image(original_path, dest_path):
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
                self.storage.delete_image(original_path, delete_data=True)
            
            self._refresh_image_list()
