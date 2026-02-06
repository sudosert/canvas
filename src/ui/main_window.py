"""Main application window."""
import os
import json
from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QProgressDialog,
    QMenuBar, QMenu, QToolBar, QStatusBar, QLabel, QProgressBar, QTabWidget,
    QPushButton
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from ..core.image_scanner import ImageScanner
from ..core.image_index import ImageIndex
from ..core.metadata_cache import MetadataCache
from ..core.metadata_parser import MetadataParser
from ..models.image_data import ImageMetadata
from .paginated_thumbnail_grid import PaginatedThumbnailGrid
from .image_viewer import ImageViewer
from .metadata_panel import MetadataPanel
from .filter_bar import FilterBar
from .slideshow_dialog import SlideshowDialog
from .image_storage_dialog import ImageStorageDialog
from .folder_loader import FolderLoaderThread
from .filesystem_browser import FilesystemBrowser
from .settings_dialog import SettingsDialog
from .collections_panel import CollectionsPanel


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, skip_db_update: bool = False):
        super().__init__()
        self.setWindowTitle("SD Image Viewer")
        self.setMinimumSize(1750, 1125)  # 25% larger than 1400x900
        self.resize(2000, 1250)  # 25% larger than 1600x1000
        
        # Store configuration
        self.skip_db_update = skip_db_update
        
        # Initialize data
        self.image_index = ImageIndex()
        self.metadata_cache = MetadataCache()
        self.current_folder: Optional[str] = None
        self.filtered_images: List[ImageMetadata] = []
        self.current_image_index: int = -1
        self.fullscreen_viewer: Optional[ImageViewer] = None
        self.slideshow_dialog: Optional[SlideshowDialog] = None
        self.slideshow_random = False
        self.slideshow_order: List[int] = []
        self.slideshow_position = 0
        self.loader_thread: Optional[FolderLoaderThread] = None
        self.loading_progress_bar: Optional[QProgressBar] = None
        self._current_image_path: Optional[str] = None
        
        # Load settings
        self.settings = QSettings("SDImageViewer", "Settings")
        self.use_metadata_cache = self.settings.value("use_metadata_cache", False, type=bool)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()
        # Don't load last folder automatically - let main.py handle it after UI is shown
        # self._load_last_folder()
    
    def _setup_ui(self):
        """Set up the main UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Filter bar
        self.filter_bar = FilterBar()
        self.filter_bar.filter_changed.connect(self._apply_filters)
        self.filter_bar.sort_changed.connect(self._apply_filters)
        layout.addWidget(self.filter_bar)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)  # Allow panels to be collapsed by user
        
        # Left: Tab widget with thumbnails and filesystem browser
        self.left_tabs = QTabWidget()
        self.left_tabs.setMinimumWidth(300)
        
        # Gallery tab (formerly Thumbnails)
        self.thumbnail_grid = PaginatedThumbnailGrid()
        self.thumbnail_grid.image_selected.connect(self._on_thumbnail_selected)
        
        # Add sort controls above the gallery
        sort_controls = self.filter_bar.create_sort_controls()
        self.thumbnail_grid.set_sort_controls(sort_controls)
        
        self.left_tabs.addTab(self.thumbnail_grid, "🖼️ Gallery")
        
        # Filesystem browser tab
        self.filesystem_browser = FilesystemBrowser()
        self.filesystem_browser.folder_selected.connect(self._on_filesystem_folder_selected)
        self.filesystem_browser.file_selected.connect(self._on_filesystem_file_selected)
        self.filesystem_browser.file_selected.connect(self._on_filesystem_file_selected)
        self.left_tabs.addTab(self.filesystem_browser, "📁 Browse")
        
        # Collections tab
        self.collections_panel = CollectionsPanel()
        self.left_tabs.addTab(self.collections_panel, "📚 Collections")
        
        # Gallery container with collapse button
        self.gallery_container = QWidget()
        gallery_layout = QHBoxLayout(self.gallery_container)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_layout.setSpacing(0)
        
        # Collapse/expand button
        self.gallery_toggle_btn = QPushButton("◀")
        self.gallery_toggle_btn.setFixedWidth(20)
        self.gallery_toggle_btn.setToolTip("Collapse gallery panel")
        self.gallery_toggle_btn.clicked.connect(self._toggle_gallery_panel)
        self.gallery_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #888;
                border: none;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #fff;
            }
        """)
        gallery_layout.addWidget(self.gallery_toggle_btn)
        gallery_layout.addWidget(self.left_tabs)
        
        splitter.addWidget(self.gallery_container)
        
        # Middle: Image viewer
        self.image_viewer = ImageViewer()
        self.image_viewer.setMinimumWidth(300)
        splitter.addWidget(self.image_viewer)
        
        # Right: Metadata panel with collapse button
        self.metadata_container = QWidget()
        metadata_layout = QHBoxLayout(self.metadata_container)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(0)
        
        # Collapse/expand button
        self.metadata_toggle_btn = QPushButton("◀")
        self.metadata_toggle_btn.setFixedWidth(20)
        self.metadata_toggle_btn.setToolTip("Collapse metadata panel")
        self.metadata_toggle_btn.clicked.connect(self._toggle_metadata_panel)
        self.metadata_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #888;
                border: none;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #fff;
            }
        """)
        metadata_layout.addWidget(self.metadata_toggle_btn)
        
        # Metadata panel
        self.metadata_panel = MetadataPanel()
        self.metadata_panel.setMinimumWidth(300)
        metadata_layout.addWidget(self.metadata_panel)
        
        splitter.addWidget(self.metadata_container)
        
        # Set stretch factors for equal resizing
        splitter.setStretchFactor(0, 1)  # Thumbnail grid - equal
        splitter.setStretchFactor(1, 1)  # Image viewer - equal
        splitter.setStretchFactor(2, 1)  # Metadata panel - equal
        
        # Set initial splitter proportions (equal thirds)
        total_width = 2000  # Default window width
        equal_size = total_width // 3
        splitter.setSizes([equal_size, equal_size, equal_size])
        
        layout.addWidget(splitter, 1)  # Add stretch factor to take all available space
        
        # Status bar with progress indicator
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add progress bar to status bar (hidden by default)
        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setMaximumWidth(200)
        self.loading_progress_bar.setMaximumHeight(16)
        self.loading_progress_bar.setTextVisible(True)
        self.loading_progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.loading_progress_bar)
        
        self.status_bar.showMessage("Ready")
        
        # Connect collections panel signals (after status_bar is created)
        self.collections_panel.apply_collection_filters.connect(self._on_collection_filters_applied)
        self.collections_panel.set_thumbnail_requested.connect(self._on_set_collection_thumbnail)
        self.collections_panel.status_message.connect(self.status_bar.showMessage)
        self.collections_panel.switch_to_gallery.connect(lambda: self.left_tabs.setCurrentIndex(0))
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
                color: #eee;
            }
            QMenuBar {
                background-color: #2a2a2a;
                color: #eee;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #4a9eff;
            }
            QToolBar {
                background-color: #252525;
                border: none;
                padding: 5px;
            }
            QStatusBar {
                background-color: #252525;
                color: #888;
            }
            QSplitter::handle {
                background-color: #333;
            }
            QSplitter::handle:horizontal {
                width: 4px;
            }
        """)
    
    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Folder...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        slideshow_action = QAction("&Slideshow...", self)
        slideshow_action.setShortcut(QKeySequence("F5"))
        slideshow_action.triggered.connect(self._show_slideshow_dialog)
        view_menu.addAction(slideshow_action)
        
        view_menu.addSeparator()
        
        # Metadata cache toggle
        self.cache_action = QAction("Use Metadata Cache", self)
        self.cache_action.setCheckable(True)
        self.cache_action.setChecked(self.use_metadata_cache)
        self.cache_action.triggered.connect(self._toggle_metadata_cache)
        view_menu.addAction(self.cache_action)
        
        # Clear cache action
        clear_cache_action = QAction("Clear Metadata Cache", self)
        clear_cache_action.triggered.connect(self._clear_metadata_cache)
        view_menu.addAction(clear_cache_action)
        
        view_menu.addSeparator()
        
        # Image Storage Manager
        storage_action = QAction("Image Storage Manager...", self)
        storage_action.triggered.connect(self._show_storage_manager)
        view_menu.addAction(storage_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        # Refresh metadata actions
        refresh_current_action = QAction("Refresh Current Images Metadata", self)
        refresh_current_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_current_action.triggered.connect(self._refresh_current_metadata)
        tools_menu.addAction(refresh_current_action)
        
        refresh_all_action = QAction("Refresh All Database Metadata", self)
        refresh_all_action.triggered.connect(self._refresh_all_metadata)
        tools_menu.addAction(refresh_all_action)

        tools_menu.addSeparator()

        # Rescan actions
        rescan_new_action = QAction("Rescan for New Files", self)
        rescan_new_action.triggered.connect(self._rescan_new_files)
        tools_menu.addAction(rescan_new_action)

        rescan_all_action = QAction("Rescan All Files", self)
        rescan_all_action.triggered.connect(self._rescan_all_files)
        tools_menu.addAction(rescan_all_action)

        tools_menu.addSeparator()

        # Settings
        settings_action = QAction("Settings...", self)
        settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        settings_action.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Open folder button
        open_btn = QAction("📁 Open", self)
        open_btn.triggered.connect(self._open_folder)
        toolbar.addAction(open_btn)
        
        toolbar.addSeparator()
        
        # Navigation buttons
        prev_btn = QAction("◀ Prev", self)
        prev_btn.triggered.connect(self._show_previous_image)
        toolbar.addAction(prev_btn)
        
        next_btn = QAction("Next ▶", self)
        next_btn.triggered.connect(self._show_next_image)
        toolbar.addAction(next_btn)
        
        toolbar.addSeparator()
        
        # View buttons
        fullscreen_btn = QAction("⛶ Fullscreen", self)
        fullscreen_btn.triggered.connect(self._toggle_fullscreen)
        toolbar.addAction(fullscreen_btn)
        
        slideshow_btn = QAction("▶ Slideshow", self)
        slideshow_btn.triggered.connect(self._show_slideshow_dialog)
        toolbar.addAction(slideshow_btn)
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Navigation
        QShortcut(QKeySequence("Left"), self, self._show_previous_image)
        QShortcut(QKeySequence("Right"), self, self._show_next_image)
        
        # Zoom
        QShortcut(QKeySequence("Ctrl++"), self, self.image_viewer.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.image_viewer.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.image_viewer.reset_zoom)
        
        # Escape to exit fullscreen
        QShortcut(QKeySequence("Escape"), self, self._exit_fullscreen)
    
    def _load_last_folder(self):
        """Load the last opened folder from settings."""
        last_folder = self.settings.value("last_folder", "")
        if last_folder and os.path.exists(last_folder):
            self._load_folder(last_folder, recursive=True)
    
    def _open_folder(self):
        """Open a folder dialog and load images."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Image Folder",
            self.settings.value("last_folder", "")
        )
        
        if folder:
            self._load_folder(folder)
    
    def _load_folder(self, folder: str, recursive: bool = True):
        """Load images from a folder asynchronously."""
        print(f"[DEBUG] Starting to load folder: {folder} (recursive={recursive})")
        self.current_folder = folder
        self.settings.setValue("last_folder", folder)
        
        # Clear existing index
        print("[DEBUG] Clearing existing index...")
        self.image_index.clear()
        self.filtered_images = []
        self.current_image_index = -1
        self.thumbnail_grid.set_images([])  # Clear thumbnails
        
        # Show loading indicator
        self.loading_progress_bar.setVisible(True)
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate
        self.status_bar.showMessage("Loading images...")
        
        # Cancel any existing loader
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait()
        
        # Create and start loader thread
        self.loader_thread = FolderLoaderThread(
            folder,
            use_cache=self.use_metadata_cache,
            skip_validation=self.skip_db_update,
            recursive=recursive
        )
        
        # Connect signals
        self.loader_thread.progress_update.connect(self._on_loading_progress)
        self.loader_thread.loading_complete.connect(self._on_loading_complete)
        self.loader_thread.loading_failed.connect(self._on_loading_failed)
        
        # Start loading
        self.loader_thread.start()
    
    def _on_loading_progress(self, current: int, total: int, message: str):
        """Handle loading progress updates."""
        self.status_bar.showMessage(message)
        self.loading_progress_bar.setVisible(True)
        if total > 0:
            self.loading_progress_bar.setRange(0, total)
            self.loading_progress_bar.setValue(current)
        else:
            self.loading_progress_bar.setRange(0, 0)  # Indeterminate
    
    def _on_loading_complete(self, images: List[ImageMetadata]):
        """Handle successful loading completion."""
        print(f"[DEBUG] Loading complete, got {len(images)} images")
        
        # Hide loading indicator
        self.loading_progress_bar.setVisible(False)
        
        # Add images to index
        print("[DEBUG] Adding images to index...")
        added_count = self.image_index.add_images(images)
        print(f"[DEBUG] Added {added_count} images to index")
        
        # Apply filters and update UI
        print("[DEBUG] Applying filters...")
        self._apply_filters()
        
        # Update filesystem browser to show current folder
        if self.current_folder:
            self.filesystem_browser.set_root_path(self.current_folder)
        
        # Update status
        cache_status = " (cached)" if self.use_metadata_cache else ""
        skip_status = " [read-only]" if self.skip_db_update else ""
        self.status_bar.showMessage(
            f"Loaded {len(images)} images{cache_status}{skip_status} from {self.current_folder}",
            5000
        )
        print("[DEBUG] Load complete")
    
    def _on_loading_failed(self, error_msg: str):
        """Handle loading failure."""
        print(f"[ERROR] Loading failed: {error_msg}")
        
        # Hide loading indicator
        self.loading_progress_bar.setVisible(False)
        self.status_bar.showMessage("Loading failed", 5000)
        
        # Show error dialog
        QMessageBox.critical(
            self,
            "Error",
            f"Failed to load images:\n{error_msg}"
        )
    
    def _toggle_metadata_cache(self, enabled: bool):
        """Toggle metadata caching on/off."""
        self.use_metadata_cache = enabled
        self.settings.setValue("use_metadata_cache", enabled)
        self.cache_action.setChecked(enabled)
        
        status = "enabled" if enabled else "disabled"
        self.status_bar.showMessage(f"Metadata cache {status}", 3000)
        print(f"[DEBUG] Metadata cache {status}")
    
    def _clear_metadata_cache(self):
        """Clear all metadata caches."""
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all metadata caches?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.metadata_cache.clear_cache():
                self.status_bar.showMessage("Metadata cache cleared", 3000)
            else:
                self.status_bar.showMessage("Failed to clear cache", 3000)
    
    def _show_storage_manager(self):
        """Show the image storage manager dialog."""
        dialog = ImageStorageDialog(self, skip_update=self.skip_db_update)
        dialog.exec()
    
    def _show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Settings were saved, show confirmation
            self.status_bar.showMessage("Settings saved", 3000)
    
    def _refresh_current_metadata(self):
        """Refresh metadata for currently loaded images."""
        if not self.current_folder or not self.filtered_images:
            QMessageBox.information(
                self,
                "No Images",
                "No images are currently loaded."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Refresh Metadata",
            f"Re-parse metadata for {len(self.filtered_images)} currently loaded images?\n\n"
            "This will re-read the image files and update the metadata cache.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Show progress
            progress = QProgressDialog(
                "Refreshing metadata...",
                "Cancel",
                0,
                len(self.filtered_images),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            refreshed = 0
            for i, img_metadata in enumerate(self.filtered_images):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f"Refreshing {img_metadata.file_name}...")
                
                # Re-parse the image
                new_metadata = MetadataParser.parse_image(img_metadata.file_path)
                
                # Update in index
                self.image_index.add_image(new_metadata)
                refreshed += 1
            
            progress.close()
            
            # Save to cache
            if self.use_metadata_cache:
                all_images = self.image_index.get_all_images()
                self.metadata_cache.save_cache(self.current_folder, all_images)
            
            # Reload display
            self._apply_filters()
            
            QMessageBox.information(
                self,
                "Refresh Complete",
                f"Refreshed metadata for {refreshed} images."
            )
    
    def _refresh_all_metadata(self):
        """Refresh metadata for all images in the database."""
        reply = QMessageBox.question(
            self,
            "Refresh All Metadata",
            "Re-parse metadata for ALL images in the current folder?\n\n"
            "This may take a while for large collections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Get all images from index
            all_images = self.image_index.get_all_images()
            
            if not all_images:
                QMessageBox.information(self, "No Images", "No images in database.")
                return
            
            # Show progress
            progress = QProgressDialog(
                "Refreshing all metadata...",
                "Cancel",
                0,
                len(all_images),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            refreshed = 0
            for i, img_metadata in enumerate(all_images):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f"Refreshing {img_metadata.file_name}...")
                
                # Re-parse the image
                new_metadata = MetadataParser.parse_image(img_metadata.file_path)
                
                # Update in index
                self.image_index.add_image(new_metadata)
                refreshed += 1
            
            progress.close()
            
            # Save to cache
            if self.use_metadata_cache and self.current_folder:
                all_images = self.image_index.get_all_images()
                self.metadata_cache.save_cache(self.current_folder, all_images)
            
            # Reload display
            self._apply_filters()
            
            QMessageBox.information(
                self,
                "Refresh Complete",
                f"Refreshed metadata for {refreshed} images."
            )

    def _rescan_new_files(self):
        """Rescan for new files in the current folder."""
        if not self.current_folder:
            QMessageBox.information(
                self,
                "No Folder",
                "No folder is currently loaded."
            )
            return

        reply = QMessageBox.question(
            self,
            "Rescan for New Files",
            f"Scan for new files in {self.current_folder}?\n\n"
            "This will add any new images found without re-parsing existing ones.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Show progress
            progress = QProgressDialog(
                "Scanning for new files...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            # Get existing file paths
            existing_paths = set(img.file_path for img in self.image_index.get_all_images())

            def progress_callback(current, total):
                if progress.wasCanceled():
                    return False
                progress.setValue(int((current / total) * 100))
                progress.setLabelText(f"Scanning... {current}/{total}")
                return True

            # Scan directory for new files
            new_files = []
            scanner = ImageScanner(progress_callback=progress_callback)

            all_images = scanner.scan_directory(self.current_folder, recursive=True)

            # Find new files
            for img_metadata in all_images:
                if img_metadata.file_path not in existing_paths:
                    new_files.append(img_metadata)

            progress.close()

            if not new_files:
                QMessageBox.information(
                    self,
                    "No New Files",
                    "No new images found."
                )
                return

            # Add new files to index
            for img_metadata in new_files:
                self.image_index.add_image(img_metadata)

            # Save to cache
            if self.use_metadata_cache:
                all_images = self.image_index.get_all_images()
                self.metadata_cache.save_cache(self.current_folder, all_images)

            # Reload display
            self._apply_filters()

            QMessageBox.information(
                self,
                "Rescan Complete",
                f"Added {len(new_files)} new images."
            )

    def _rescan_all_files(self):
        """Rescan all files in the current folder, flushing all metadata."""
        if not self.current_folder:
            QMessageBox.information(
                self,
                "No Folder",
                "No folder is currently loaded."
            )
            return

        reply = QMessageBox.question(
            self,
            "Rescan All Files",
            f"Rescan all files in {self.current_folder}?\n\n"
            "This will flush all metadata and re-parse every image file.\n"
            "This may take a while for large collections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear the index
            self.image_index.clear()

            # Clear the cache for this folder
            self.metadata_cache.clear_cache(self.current_folder)

            # Show progress
            progress = QProgressDialog(
                "Rescanning all files...",
                "Cancel",
                0,
                100,
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)

            # Scan directory
            scanner = ImageScanner()

            def progress_callback(current, total):
                if progress.wasCanceled():
                    return False
                progress.setValue(int((current / total) * 100))
                progress.setLabelText(f"Scanning... {current}/{total}")
                return True

            all_images = scanner.scan_directory(self.current_folder, recursive=True, progress_callback=progress_callback)

            progress.close()

            if not all_images:
                QMessageBox.information(
                    self,
                    "No Images",
                    "No images found in the folder."
                )
                return

            # Add all images to index
            for img_metadata in all_images:
                self.image_index.add_image(img_metadata)

            # Save to cache
            if self.use_metadata_cache:
                self.metadata_cache.save_cache(self.current_folder, all_images)

            # Reload display
            self._apply_filters()

            QMessageBox.information(
                self,
                "Rescan Complete",
                f"Rescanned {len(all_images)} images."
            )

    def _apply_filters(self):
        """Apply current filter and sort settings."""
        print("[DEBUG] Applying filters...")
        include_terms = self.filter_bar.get_include_terms()
        exclude_terms = self.filter_bar.get_exclude_terms()
        sort_by = self.filter_bar.get_sort_by()
        reverse = self.filter_bar.get_reverse_sort()
        orientation = self.filter_bar.get_orientation_filters()
        print(f"[DEBUG] Include terms: {include_terms}")
        print(f"[DEBUG] Exclude terms: {exclude_terms}")
        print(f"[DEBUG] Sort by: {sort_by}, Reverse: {reverse}")
        print(f"[DEBUG] Orientation: {orientation}")
        
        # Update collections panel with current filters
        self.collections_panel.update_current_filters(
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            sort_by=sort_by,
            reverse_sort=reverse
        )
        
        # Show loading indicator for sorting
        self.status_bar.showMessage(f"Sorting images by {sort_by}...")
        self.loading_progress_bar.setVisible(True)
        self.loading_progress_bar.setRange(0, 0)  # Indeterminate
        
        # Process events to show loading indicator immediately
        from PyQt6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        
        # Get filtered and sorted images from index
        print("[DEBUG] Querying image index...")
        self.filtered_images = self.image_index.filter_images(
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            sort_by=sort_by,
            reverse=reverse,
            orientation=orientation
        )
        print(f"[DEBUG] Got {len(self.filtered_images)} filtered images")
        
        # Update UI
        print("[DEBUG] Updating thumbnail grid...")
        self._populate_thumbnail_grid()
        
        # Update filter bar with counts
        total = len(self.image_index.get_all_images())
        filtered = len(self.filtered_images)
        self.filter_bar.set_results_count(filtered, total)
        
        # Hide loading indicator
        self.loading_progress_bar.setVisible(False)
        
        # Reset current index
        self.current_image_index = -1
        if self.filtered_images:
            print("[DEBUG] Showing first image...")
            self._show_image_at_index(0)
        else:
            print("[DEBUG] No images to show")
    
    def _on_thumbnail_selected(self, file_path: str):
        """Handle thumbnail selection."""
        # Find index in filtered list
        for i, img in enumerate(self.filtered_images):
            if img.file_path == file_path:
                self._show_image_at_index(i)
                break
    
    def _on_filesystem_folder_selected(self, folder_path: str, include_subfolders: bool = True):
        """Handle folder selection from filesystem browser."""
        print(f"[DEBUG] Filesystem folder selected: {folder_path} (include_subfolders={include_subfolders})")
        # Load the selected folder
        self._load_folder(folder_path, recursive=include_subfolders)
        # Switch to gallery tab to show results
        self.left_tabs.setCurrentIndex(0)
    
    def _on_filesystem_file_selected(self, file_path: str):
        """Handle file selection from filesystem browser."""
        print(f"[DEBUG] Filesystem file selected: {file_path}")
        # If it's an image file, try to show it
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Check if it's in the current filtered images
            for i, img in enumerate(self.filtered_images):
                if img.file_path == file_path:
                    self._show_image_at_index(i)
                    # Switch to gallery tab
                    self.left_tabs.setCurrentIndex(0)
                    return
            
            # If not in filtered images, load its parent folder
            parent_folder = os.path.dirname(file_path)
            self._load_folder(parent_folder)
            # Switch to gallery tab
            self.left_tabs.setCurrentIndex(0)
    
    def _on_collection_filters_applied(self, name: str, include_terms: list,
                                       exclude_terms: list, sort_by: str, reverse: bool):
        """Handle collection filter application."""
        print(f"[DEBUG] Applying collection filters: {name}")
        
        # Set the filter bar values
        self.filter_bar.include_input.setText(', '.join(include_terms))
        self.filter_bar.exclude_input.setText(', '.join(exclude_terms))
        
        # Set sort values if external controls exist
        if hasattr(self.filter_bar, '_external_sort_combo'):
            # Map sort_by value to display text
            sort_display = {v: k for k, v in self.filter_bar.SORT_OPTIONS.items()}
            self.filter_bar._external_sort_combo.setCurrentText(sort_display.get(sort_by, 'Date'))
        if hasattr(self.filter_bar, '_external_reverse_checkbox'):
            self.filter_bar._external_reverse_checkbox.setChecked(reverse)
        
        # Apply the filters
        self._apply_filters()
        
        # Switch to gallery tab
        self.left_tabs.setCurrentIndex(0)
    
    def _on_set_collection_thumbnail(self, collection_name: str):
        """Handle request to set collection thumbnail from current image."""
        if hasattr(self, '_current_image_path') and self._current_image_path:
            self.collections_panel.set_collection_thumbnail(collection_name, self._current_image_path)
        else:
            self.status_bar.showMessage("Select an image first to set as thumbnail", 3000)
    
    def _populate_thumbnail_grid(self):
        """Populate thumbnail grid with current filtered images."""
        print(f"[DEBUG] Populating thumbnail grid with {len(self.filtered_images)} images")
        try:
            # Disconnect and reconnect the signal to avoid duplicates
            try:
                self.thumbnail_grid.image_selected.disconnect(self._on_thumbnail_selected)
            except:
                pass
            self.thumbnail_grid.set_images(self.filtered_images)
            self.thumbnail_grid.image_selected.connect(self._on_thumbnail_selected)
            print("[DEBUG] Thumbnail grid populated successfully")
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to populate thumbnail grid: {e}")
            print(traceback.format_exc())
    
    def _show_image_at_index(self, index: int):
        """Show image at the given index."""
        print(f"[DEBUG] Showing image at index {index}")
        if not self.filtered_images:
            print("[DEBUG] No filtered images available")
            return
        if index < 0 or index >= len(self.filtered_images):
            print(f"[DEBUG] Index {index} out of range (0-{len(self.filtered_images)-1})")
            return
        
        self.current_image_index = index
        metadata = self.filtered_images[index]
        print(f"[DEBUG] Loading image: {metadata.file_path}")
        
        # Create a copy of metadata for debugging, excluding heavy workflow data
        debug_meta = metadata.to_dict()
        if 'extra_params' in debug_meta and isinstance(debug_meta['extra_params'], str):
            try:
                params = json.loads(debug_meta['extra_params'])
                params.pop('workflow', None)
                params.pop('workflow_raw', None)
                params.pop('workflow_nodes', None)
                debug_meta['extra_params'] = params
            except:
                pass
        
        print(f"[DEBUG] Metadata: {json.dumps(debug_meta, indent=2)}")
        
        try:
            # Update viewer
            self.image_viewer.load_image(metadata.file_path)
            
            # Update metadata panel
            self.metadata_panel.set_metadata(metadata)
            
            # Update thumbnail selection
            self.thumbnail_grid.select_image(metadata.file_path)
            
            # Update status
            self.status_bar.showMessage(
                f"Image {index + 1} of {len(self.filtered_images)}: {metadata.file_name}"
            )
            print(f"[DEBUG] Successfully displayed image: {metadata.file_name}")
            
            # Store current image path for collections thumbnail feature
            self._current_image_path = metadata.file_path
        except Exception as e:
            import traceback
            print(f"[ERROR] Failed to show image: {e}")
            print(traceback.format_exc())
        self.status_bar.showMessage(
            f"Image {index + 1} of {len(self.filtered_images)}: {metadata.file_name}"
        )
    
    def _show_previous_image(self):
        """Show the previous image."""
        if not self.filtered_images:
            return
        
        new_index = self.current_image_index - 1
        if new_index < 0:
            new_index = len(self.filtered_images) - 1  # Wrap around
        
        self._show_image_at_index(new_index)
    
    def _show_next_image(self):
        """Show the next image."""
        if not self.filtered_images:
            return
        
        new_index = self.current_image_index + 1
        if new_index >= len(self.filtered_images):
            new_index = 0  # Wrap around
        
        self._show_image_at_index(new_index)
    
    def _toggle_metadata_panel(self):
        """Toggle the metadata panel visibility."""
        if self.metadata_panel.isVisible():
            self.metadata_panel.hide()
            self.metadata_toggle_btn.setText("▶")
            self.metadata_toggle_btn.setToolTip("Expand metadata panel")
            self.metadata_container.setFixedWidth(20)
        else:
            self.metadata_panel.show()
            self.metadata_toggle_btn.setText("◀")
            self.metadata_toggle_btn.setToolTip("Collapse metadata panel")
            self.metadata_container.setMinimumWidth(320)
            self.metadata_container.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
    
    def _toggle_gallery_panel(self):
        """Toggle the gallery panel visibility."""
        if self.left_tabs.isVisible():
            self.left_tabs.hide()
            self.gallery_toggle_btn.setText("▶")
            self.gallery_toggle_btn.setToolTip("Expand gallery panel")
            self.gallery_container.setFixedWidth(20)
        else:
            self.left_tabs.show()
            self.gallery_toggle_btn.setText("◀")
            self.gallery_toggle_btn.setToolTip("Collapse gallery panel")
            self.gallery_container.setMinimumWidth(320)
            self.gallery_container.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.fullscreen_viewer:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()
    
    def _enter_fullscreen(self):
        """Enter fullscreen mode."""
        if not self.filtered_images or self.current_image_index < 0:
            return
        
        # Create fullscreen viewer
        self.fullscreen_viewer = ImageViewer()
        self.fullscreen_viewer.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )
        self.fullscreen_viewer.showFullScreen()
        
        # Load current image
        metadata = self.filtered_images[self.current_image_index]
        self.fullscreen_viewer.load_image(metadata.file_path)
        
        # Connect click to exit
        self.fullscreen_viewer.mousePressEvent = lambda e: self._exit_fullscreen()
    
    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if self.fullscreen_viewer:
            self.fullscreen_viewer.close()
            self.fullscreen_viewer = None
    
    def _show_slideshow_dialog(self):
        """Show the slideshow control dialog."""
        if not self.slideshow_dialog:
            self.slideshow_dialog = SlideshowDialog(self)
            self.slideshow_dialog.start_slideshow.connect(self._start_slideshow)
            self.slideshow_dialog.stop_slideshow.connect(self._stop_slideshow)
            self.slideshow_dialog.next_image.connect(self._show_next_image)
            self.slideshow_dialog.previous_image.connect(self._show_previous_image)
        
        self.slideshow_dialog.show()
        self.slideshow_dialog.raise_()
    
    def _start_slideshow(self, interval_ms: int, random_order: bool):
        """Start slideshow mode."""
        self.slideshow_random = random_order
        
        if random_order:
            import random
            self.slideshow_order = list(range(len(self.filtered_images)))
            random.shuffle(self.slideshow_order)
            self.slideshow_position = 0
    
    def _stop_slideshow(self):
        """Stop slideshow mode."""
        self.slideshow_random = False
        self.slideshow_order = []
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About SD Image Viewer",
            """<h2>SD Image Viewer</h2>
            <p>A desktop image viewer for Stable Diffusion generated images.</p>
            <p>Features:</p>
            <ul>
                <li>Metadata extraction from A1111 and ComfyUI images</li>
                <li>Prompt-based filtering (include/exclude)</li>
                <li>Fullscreen and slideshow modes</li>
                <li>Fast thumbnail browsing</li>
            </ul>
            <p>Built with Python and PyQt6.</p>
            """
        )
    
    def closeEvent(self, event):
        """Handle window close."""
        # Stop slideshow if running
        if self.slideshow_dialog and self.slideshow_dialog.is_playing:
            self.slideshow_dialog._stop_slideshow()
        
        # Save settings
        self.settings.sync()
        
        event.accept()
