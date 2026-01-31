"""Main application window."""
import os
from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QProgressDialog,
    QMenuBar, QMenu, QToolBar, QStatusBar, QLabel
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from ..core.image_scanner import ImageScanner
from ..core.image_index import ImageIndex
from ..models.image_data import ImageMetadata
from .paginated_thumbnail_grid import PaginatedThumbnailGrid
from .image_viewer import ImageViewer
from .metadata_panel import MetadataPanel
from .filter_bar import FilterBar
from .slideshow_dialog import SlideshowDialog


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SD Image Viewer")
        self.setMinimumSize(1200, 800)
        
        # Initialize data
        self.image_index = ImageIndex()
        self.current_folder: Optional[str] = None
        self.filtered_images: List[ImageMetadata] = []
        self.current_image_index: int = -1
        self.fullscreen_viewer: Optional[ImageViewer] = None
        self.slideshow_dialog: Optional[SlideshowDialog] = None
        self.slideshow_random = False
        self.slideshow_order: List[int] = []
        self.slideshow_position = 0
        
        # Load settings
        self.settings = QSettings("SDImageViewer", "Settings")
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._load_last_folder()
    
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
        layout.addWidget(self.filter_bar)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)  # Prevent panels from being collapsed
        
        # Left: Thumbnail grid (paginated)
        self.thumbnail_grid = PaginatedThumbnailGrid()
        self.thumbnail_grid.image_selected.connect(self._on_thumbnail_selected)
        self.thumbnail_grid.setMinimumWidth(250)
        self.thumbnail_grid.setMaximumWidth(600)
        splitter.addWidget(self.thumbnail_grid)
        
        # Middle: Image viewer
        self.image_viewer = ImageViewer()
        self.image_viewer.setMinimumWidth(400)
        splitter.addWidget(self.image_viewer)
        
        # Right: Metadata panel
        self.metadata_panel = MetadataPanel()
        self.metadata_panel.setMinimumWidth(250)
        self.metadata_panel.setMaximumWidth(500)
        splitter.addWidget(self.metadata_panel)
        
        # Set stretch factors for proportional resizing
        splitter.setStretchFactor(0, 0)  # Thumbnail grid - fixed preferrence
        splitter.setStretchFactor(1, 1)  # Image viewer - takes extra space
        splitter.setStretchFactor(2, 0)  # Metadata panel - fixed preferrence
        
        # Set initial splitter proportions
        splitter.setSizes([300, 700, 300])
        
        layout.addWidget(splitter, 1)  # Add stretch factor to take all available space
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
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
            self._load_folder(last_folder)
    
    def _open_folder(self):
        """Open a folder dialog and load images."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Image Folder",
            self.settings.value("last_folder", "")
        )
        
        if folder:
            self._load_folder(folder)
    
    def _load_folder(self, folder: str):
        """Load images from a folder."""
        print(f"[DEBUG] Starting to load folder: {folder}")
        self.current_folder = folder
        self.settings.setValue("last_folder", folder)
        
        # Count images first
        print("[DEBUG] Counting images...")
        scanner = ImageScanner()
        count = scanner.count_images(folder)
        print(f"[DEBUG] Found {count} images")
        
        if count == 0:
            QMessageBox.information(
                self,
                "No Images",
                f"No PNG or JPEG images found in:\n{folder}"
            )
            return
        
        # Show progress dialog
        progress = QProgressDialog(
            f"Loading {count} images...",
            "Cancel",
            0,
            count,
            self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        
        # Clear existing index
        print("[DEBUG] Clearing existing index...")
        self.image_index.clear()
        self.filtered_images = []
        self.current_image_index = -1
        
        # Scan with progress updates
        def progress_callback(current, total):
            progress.setValue(current)
            if progress.wasCanceled():
                print(f"[DEBUG] Loading cancelled at {current}/{total}")
                return False
            return True
        
        scanner = ImageScanner(progress_callback=progress_callback)
        
        try:
            print("[DEBUG] Starting scan...")
            images = scanner.scan_directory(folder)
            print(f"[DEBUG] Scan complete, got {len(images)} images")
            
            if not progress.wasCanceled():
                print("[DEBUG] Adding images to index...")
                added_count = self.image_index.add_images(images)
                print(f"[DEBUG] Added {added_count} images to index")
                
                print("[DEBUG] Applying filters...")
                # Apply filters and update UI
                self._apply_filters()
                
                self.status_bar.showMessage(
                    f"Loaded {len(images)} images from {folder}",
                    5000
                )
                print("[DEBUG] Load complete")
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            print(f"[ERROR] Failed to load images: {error_msg}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load images:\n{str(e)}"
            )
        
        progress.close()
    
    def _apply_filters(self):
        """Apply current filter settings."""
        print("[DEBUG] Applying filters...")
        include_terms = self.filter_bar.get_include_terms()
        exclude_terms = self.filter_bar.get_exclude_terms()
        print(f"[DEBUG] Include terms: {include_terms}")
        print(f"[DEBUG] Exclude terms: {exclude_terms}")
        
        # Get filtered images from index
        print("[DEBUG] Querying image index...")
        self.filtered_images = self.image_index.filter_images(
            include_terms=include_terms,
            exclude_terms=exclude_terms
        )
        print(f"[DEBUG] Got {len(self.filtered_images)} filtered images")
        
        # Update UI
        print("[DEBUG] Updating thumbnail grid...")
        self._populate_thumbnail_grid()
        
        # Update filter bar with counts
        total = len(self.image_index.get_all_images())
        filtered = len(self.filtered_images)
        self.filter_bar.set_results_count(filtered, total)
        
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
