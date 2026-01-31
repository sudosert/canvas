"""Image viewer widget for displaying images at full resolution."""
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QMouseEvent

from ..utils.image_cache import ImageCache


class ImageViewer(QWidget):
    """Widget for viewing images with zoom and pan support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap: Optional[QPixmap] = None
        self.current_file_path: Optional[str] = None
        self.zoom_level = 1.0
        self.image_cache = ImageCache(max_cache_size=10)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1a1a1a;
            }
        """)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
            }
        """)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        
        # Info label
        self.info_label = QLabel("No image loaded")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #ccc;
                padding: 5px;
            }
        """)
        layout.addWidget(self.info_label)
        
        # Set focus policy for keyboard events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def load_image(self, file_path: str):
        """
        Load and display an image.
        
        Args:
            file_path: Path to the image file
        """
        self.current_file_path = file_path
        self.zoom_level = 1.0
        
        # Try to get from cache first
        pixmap = self.image_cache.get(file_path)
        
        if not pixmap:
            # Load directly
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.image_cache.get(file_path)  # Add to cache
        
        if pixmap and not pixmap.isNull():
            self.current_pixmap = pixmap
            self._update_display()
            self.info_label.setText(
                f"{pixmap.width()}x{pixmap.height()} | "
                f"Zoom: {int(self.zoom_level * 100)}%"
            )
        else:
            self.current_pixmap = None
            self.image_label.setText("Failed to load image")
            self.info_label.setText("Error loading image")
    
    def _update_display(self):
        """Update the displayed image with current zoom level."""
        if not self.current_pixmap:
            return
        
        # Get available size with some padding
        viewport_size = self.scroll_area.viewport().size()
        available_width = max(viewport_size.width() - 40, 100)
        available_height = max(viewport_size.height() - 40, 100)
        
        if self.zoom_level == 1.0:
            # Fit to window
            scaled = self.current_pixmap.scaled(
                available_width,
                available_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            # Apply zoom
            new_size = QSize(
                int(self.current_pixmap.width() * self.zoom_level),
                int(self.current_pixmap.height() * self.zoom_level)
            )
            scaled = self.current_pixmap.scaled(
                new_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
    
    def zoom_in(self):
        """Zoom in by 25%."""
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self._update_display()
        self._update_info()
    
    def zoom_out(self):
        """Zoom out by 25%."""
        self.zoom_level = max(self.zoom_level / 1.25, 0.1)
        self._update_display()
        self._update_info()
    
    def reset_zoom(self):
        """Reset zoom to fit window."""
        self.zoom_level = 1.0
        self._update_display()
        self._update_info()
    
    def _update_info(self):
        """Update the info label."""
        if self.current_pixmap:
            self.info_label.setText(
                f"{self.current_pixmap.width()}x{self.current_pixmap.height()} | "
                f"Zoom: {int(self.zoom_level * 100)}%"
            )
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
    
    def resizeEvent(self, event):
        """Handle resize to update image display."""
        super().resizeEvent(event)
        if self.current_pixmap and self.zoom_level == 1.0:
            self._update_display()
    
    def clear(self):
        """Clear the current image."""
        self.current_pixmap = None
        self.current_file_path = None
        self.image_label.clear()
        self.info_label.setText("No image loaded")
