"""Paginated thumbnail grid with virtual scrolling."""
from typing import List, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QScrollArea, QLabel, QVBoxLayout,
    QSizePolicy, QFrame, QHBoxLayout, QPushButton, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QMouseEvent, QKeyEvent, QWheelEvent

from ..models.image_data import ImageMetadata
from ..utils.image_cache import ThumbnailCache
from ..core.thumbnail_persistence import ThumbnailPersistence


class PaginatedThumbnailGrid(QWidget):
    """
    Paginated thumbnail grid that only loads visible thumbnails.
    Uses virtual scrolling with pagination for large collections.
    """
    
    image_selected = pyqtSignal(str)  # Emits file_path when thumbnail clicked
    page_changed = pyqtSignal(int, int)  # Emits current_page, total_pages
    
    # Items per page - adjust based on typical screen size
    DEFAULT_ITEMS_PER_PAGE = 100
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails: List[ThumbnailLabel] = []
        self.current_images: List[ImageMetadata] = []
        self.selected_path: Optional[str] = None
        self.thumbnail_cache = ThumbnailCache(thumbnail_size=(200, 200))
        self.thumbnail_persistence = ThumbnailPersistence()
        
        # Pagination
        self.current_page = 0
        self.items_per_page = self.DEFAULT_ITEMS_PER_PAGE
        self.total_pages = 0
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Pagination controls
        self.pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(self.pagination_widget)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self._go_to_previous_page)
        self.prev_btn.setEnabled(False)
        pagination_layout.addWidget(self.prev_btn)
        
        pagination_layout.addStretch()
        
        self.page_label = QLabel("Page 1 of 1")
        pagination_layout.addWidget(self.page_label)
        
        # Page size selector
        pagination_layout.addWidget(QLabel("Items per page:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(50, 500)
        self.page_size_spin.setSingleStep(50)
        self.page_size_spin.setValue(self.items_per_page)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        pagination_layout.addWidget(self.page_size_spin)
        
        pagination_layout.addStretch()
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self._go_to_next_page)
        self.next_btn.setEnabled(False)
        pagination_layout.addWidget(self.next_btn)
        
        layout.addWidget(self.pagination_widget)
        
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
        
        # Style
        self.setStyleSheet("""
            PaginatedThumbnailGrid {
                background-color: #1a1a1a;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QLabel {
                color: #eee;
            }
            QSpinBox {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                padding: 5px;
            }
        """)
    
    def set_images(self, images: List[ImageMetadata]):
        """
        Set the images to display.
        
        Args:
            images: List of ImageMetadata objects
        """
        self.current_images = images
        self.current_page = 0
        self._calculate_total_pages()
        self._update_pagination_controls()
        
        if not images:
            self._clear_grid()
            self.status_label.setText("No images found")
            return
        
        self.status_label.setText(f"Showing {len(images)} images")
        self._load_current_page()
    
    def _calculate_total_pages(self):
        """Calculate total number of pages."""
        if not self.current_images:
            self.total_pages = 0
        else:
            self.total_pages = (len(self.current_images) + self.items_per_page - 1) // self.items_per_page
    
    def _update_pagination_controls(self):
        """Update pagination button states and labels."""
        self.page_label.setText(f"Page {self.current_page + 1} of {max(1, self.total_pages)}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        self.page_changed.emit(self.current_page + 1, self.total_pages)
    
    def _go_to_previous_page(self):
        """Go to the previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_pagination_controls()
            self._load_current_page()
    
    def _go_to_next_page(self):
        """Go to the next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_pagination_controls()
            self._load_current_page()
    
    def _on_page_size_changed(self, new_size: int):
        """Handle page size change."""
        self.items_per_page = new_size
        self.current_page = 0  # Reset to first page
        self._calculate_total_pages()
        self._update_pagination_controls()
        self._load_current_page()
    
    def _load_current_page(self):
        """Load thumbnails for the current page."""
        self._clear_grid()
        
        if not self.current_images:
            return
        
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.current_images))
        page_images = self.current_images[start_idx:end_idx]
        
        print(f"[DEBUG] Loading page {self.current_page + 1}: images {start_idx} to {end_idx}")
        
        columns = self._calculate_columns()
        
        for i, metadata in enumerate(page_images):
            thumbnail = ThumbnailLabel(metadata)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnails.append(thumbnail)
            
            # Load thumbnail with persistence cache
            self._load_thumbnail(thumbnail, metadata.file_path)
    
    def _clear_grid(self):
        """Clear all thumbnails from the grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.thumbnails.clear()
        self.selected_path = None
    
    def _calculate_columns(self) -> int:
        """Calculate number of columns based on available width."""
        available_width = max(self.scroll_area.viewport().width() - 20, 100)
        thumbnail_width = 220  # 200 + margins
        columns = max(1, available_width // thumbnail_width)
        return columns
    
    def resizeEvent(self, event):
        """Handle resize to recalculate columns."""
        super().resizeEvent(event)
        # Recalculate columns and reload current page if needed
        if self.current_images:
            # Store current selection
            current_selection = self.selected_path
            
            # Reload current page with new column layout
            self._clear_grid()
            self._load_current_page()
            
            # Restore selection if still on this page
            if current_selection:
                self.select_image(current_selection)
    
    def _load_thumbnail(self, thumbnail: 'ThumbnailLabel', file_path: str):
        """Load and display a thumbnail with disk caching."""
        try:
            # Try memory cache first
            pixmap = self.thumbnail_cache.get_thumbnail(file_path)
            
            if pixmap:
                self._set_thumbnail_pixmap(thumbnail, pixmap)
                return
            
            # Try disk cache
            from PIL import Image
            cached_image = self.thumbnail_persistence.get_thumbnail(file_path)
            
            if cached_image:
                # Convert PIL image to QPixmap
                import io
                data = io.BytesIO()
                cached_image.save(data, format='PNG')
                data.seek(0)
                from PyQt6.QtGui import QImage
                qimg = QImage.fromData(data.getvalue())
                pixmap = QPixmap.fromImage(qimg)
                
                # Add to memory cache
                self.thumbnail_cache.get(file_path, (200, 200))
                
                self._set_thumbnail_pixmap(thumbnail, pixmap)
                return
            
            # Load from original file
            pixmap = self.thumbnail_cache.get_thumbnail(file_path)
            
            if pixmap:
                # Save to disk cache
                with Image.open(file_path) as img:
                    self.thumbnail_persistence.save_thumbnail(file_path, img)
                
                self._set_thumbnail_pixmap(thumbnail, pixmap)
            else:
                thumbnail.setText("Failed to load")
                
        except Exception as e:
            print(f"[ERROR] Failed to load thumbnail for {file_path}: {e}")
            thumbnail.setText("Error")
    
    def _set_thumbnail_pixmap(self, thumbnail: 'ThumbnailLabel', pixmap: QPixmap):
        """Set pixmap on thumbnail with proper scaling."""
        scaled = pixmap.scaled(
            200, 200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        thumbnail.setPixmap(scaled)
    
    def _on_thumbnail_clicked(self, file_path: str):
        """Handle thumbnail click."""
        self.selected_path = file_path
        for thumb in self.thumbnails:
            thumb.selected = (thumb.file_path == file_path)
        
        self.image_selected.emit(file_path)
    
    def select_image(self, file_path: str):
        """Programmatically select an image."""
        self.selected_path = file_path
        for thumb in self.thumbnails:
            thumb.selected = (thumb.file_path == file_path)
    
    def clear(self):
        """Clear all images."""
        self._clear_grid()
        self.current_images = []
        self.current_page = 0
        self.total_pages = 0
        self._update_pagination_controls()
        self.status_label.setText("No images loaded")


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
