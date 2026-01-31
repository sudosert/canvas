"""Thumbnail grid widget for browsing images."""
from typing import List, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QScrollArea, QLabel, QVBoxLayout,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QMouseEvent, QKeyEvent

from ..models.image_data import ImageMetadata
from ..utils.image_cache import ThumbnailCache


class ThumbnailLabel(QLabel):
    """Clickable thumbnail label."""
    
    clicked = pyqtSignal(str)  # Emits file_path
    
    def __init__(self, metadata: ImageMetadata, parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.file_path = metadata.file_path
        self.setFixedSize(220, 220)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            ThumbnailLabel {
                border: 2px solid #333;
                background-color: #222;
            }
            ThumbnailLabel:hover {
                border: 2px solid #666;
            }
            ThumbnailLabel[selected="true"] {
                border: 2px solid #4a9eff;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False
    
    @property
    def selected(self) -> bool:
        return self._selected
    
    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self.setProperty("selected", "true" if value else "false")
        self.style().unpolish(self)
        self.style().polish(self)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.file_path)


class ThumbnailGrid(QWidget):
    """Grid widget for displaying image thumbnails."""
    
    image_selected = pyqtSignal(str)  # Emits file_path when thumbnail clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails: List[ThumbnailLabel] = []
        self.current_images: List[ImageMetadata] = []
        self.selected_path: Optional[str] = None
        self.thumbnail_cache = ThumbnailCache(thumbnail_size=(200, 200))
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Scroll area for thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        
        # Container widget for grid
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)
        
        # Status label
        self.status_label = QLabel("No images loaded")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def set_images(self, images: List[ImageMetadata]):
        """
        Set the images to display.
        
        Args:
            images: List of ImageMetadata objects
        """
        self.current_images = images
        self._clear_grid()
        
        if not images:
            self.status_label.setText("No images found")
            return
        
        self.status_label.setText(f"Showing {len(images)} images")
        
        # Calculate columns based on width
        self._populate_grid()
    
    def _clear_grid(self):
        """Clear all thumbnails from the grid."""
        # Remove all widgets from grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.thumbnails.clear()
        self.selected_path = None
    
    def _populate_grid(self):
        """Populate the grid with thumbnails."""
        columns = self._calculate_columns()
        print(f"[DEBUG] Populating grid with {len(self.current_images)} images, {columns} columns")
        
        # Limit initial load to prevent UI freeze with large folders
        initial_load_count = min(100, len(self.current_images))
        
        for i, metadata in enumerate(self.current_images[:initial_load_count]):
            thumbnail = ThumbnailLabel(metadata)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnails.append(thumbnail)
            
            # Load thumbnail asynchronously
            self._load_thumbnail(thumbnail, metadata.file_path)
        
        if len(self.current_images) > initial_load_count:
            print(f"[DEBUG] Loaded first {initial_load_count} thumbnails, {len(self.current_images) - initial_load_count} remaining")
            # Schedule remaining thumbnails to load in background
            QTimer.singleShot(100, lambda: self._load_remaining_thumbnails(initial_load_count))
    
    def _calculate_columns(self) -> int:
        """Calculate number of columns based on available width."""
        available_width = self.scroll_area.viewport().width() - 20
        thumbnail_width = 220  # 200 + margins
        columns = max(1, available_width // thumbnail_width)
        return columns
    
    def _load_thumbnail(self, thumbnail: ThumbnailLabel, file_path: str):
        """Load and display a thumbnail."""
        try:
            pixmap = self.thumbnail_cache.get_thumbnail(file_path)
            
            if pixmap:
                # Scale to fit while maintaining aspect ratio
                scaled = pixmap.scaled(
                    200, 200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                thumbnail.setPixmap(scaled)
            else:
                thumbnail.setText("Failed to load")
        except Exception as e:
            print(f"[ERROR] Failed to load thumbnail for {file_path}: {e}")
            thumbnail.setText("Error")
    
    def _load_remaining_thumbnails(self, start_index: int):
        """Load remaining thumbnails in batches."""
        batch_size = 50
        end_index = min(start_index + batch_size, len(self.current_images))
        columns = self._calculate_columns()
        
        print(f"[DEBUG] Loading thumbnails {start_index} to {end_index}")
        
        for i in range(start_index, end_index):
            metadata = self.current_images[i]
            thumbnail = ThumbnailLabel(metadata)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnails.append(thumbnail)
            
            # Load thumbnail
            self._load_thumbnail(thumbnail, metadata.file_path)
        
        # Schedule next batch if there are more
        if end_index < len(self.current_images):
            QTimer.singleShot(50, lambda: self._load_remaining_thumbnails(end_index))
        else:
            print("[DEBUG] All thumbnails loaded")
    
    def _on_thumbnail_clicked(self, file_path: str):
        """Handle thumbnail click."""
        # Update selection
        self.selected_path = file_path
        for thumb in self.thumbnails:
            thumb.selected = (thumb.file_path == file_path)
        
        self.image_selected.emit(file_path)
    
    def select_image(self, file_path: str):
        """Programmatically select an image."""
        self.selected_path = file_path
        for thumb in self.thumbnails:
            thumb.selected = (thumb.file_path == file_path)
    
    def resizeEvent(self, event):
        """Handle resize to adjust grid columns."""
        super().resizeEvent(event)
        if self.current_images:
            # Repopulate with new column count
            self._clear_grid()
            self._populate_grid()
    
    def clear(self):
        """Clear all images."""
        self._clear_grid()
        self.current_images = []
        self.status_label.setText("No images loaded")
