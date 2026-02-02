"""Image viewer widget for displaying images at full resolution."""
import os
import subprocess
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QHBoxLayout, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QMouseEvent

from ..utils.image_cache import ImageCache


class ImageViewer(QWidget):
    """Widget for viewing images with zoom and pan support."""
    
    zoom_mode_changed = pyqtSignal(str)  # Emits zoom mode when changed
    
    # Zoom modes
    ZOOM_FIT = 'fit'
    ZOOM_ACTUAL = 'actual'
    ZOOM_CUSTOM = 'custom'
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap: Optional[QPixmap] = None
        self.current_file_path: Optional[str] = None
        self.zoom_level = 1.0
        self.zoom_mode = self.ZOOM_FIT  # Default to fit
        self.image_cache = ImageCache(max_cache_size=10)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Zoom controls toolbar
        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(5, 2, 5, 2)
        zoom_layout.setSpacing(5)
        
        # Zoom mode selector
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_mode_combo = QComboBox()
        self.zoom_mode_combo.addItems(['Fit to Window', 'Actual Size', 'Custom'])
        self.zoom_mode_combo.setCurrentText('Fit to Window')
        self.zoom_mode_combo.currentTextChanged.connect(self._on_zoom_mode_changed)
        self.zoom_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                padding: 3px;
                border-radius: 4px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #eee;
                selection-background-color: #4a9eff;
            }
        """)
        zoom_layout.addWidget(self.zoom_mode_combo)
        
        # Zoom buttons (for custom mode)
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedSize(28, 28)
        self.zoom_out_btn.setToolTip("Zoom out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        zoom_layout.addWidget(self.zoom_out_btn)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(28, 28)
        self.zoom_in_btn.setToolTip("Zoom in")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        zoom_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_reset_btn = QPushButton("Reset")
        self.zoom_reset_btn.setToolTip("Reset zoom to fit")
        self.zoom_reset_btn.clicked.connect(self.reset_zoom)
        self.zoom_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 3px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        zoom_layout.addWidget(self.zoom_reset_btn)
        
        zoom_layout.addStretch()
        
        # Open file/folder buttons
        self.open_image_btn = QPushButton("📄 Open Image")
        self.open_image_btn.setToolTip("Open image file in default application")
        self.open_image_btn.clicked.connect(self._open_image_file)
        self.open_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 3px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a9eff;
            }
        """)
        zoom_layout.addWidget(self.open_image_btn)
        
        self.open_folder_btn = QPushButton("📁 Open Folder")
        self.open_folder_btn.setToolTip("Open containing folder in file manager")
        self.open_folder_btn.clicked.connect(self._open_containing_folder)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 3px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a9eff;
            }
        """)
        zoom_layout.addWidget(self.open_folder_btn)
        
        layout.addWidget(zoom_toolbar)
        
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
            self._update_info()
        else:
            self.current_pixmap = None
            self.image_label.setText("Failed to load image")
            self.info_label.setText("Error loading image")
    
    def _update_display(self):
        """Update the displayed image with current zoom mode."""
        if not self.current_pixmap:
            return
        
        # Get available size with some padding
        viewport_size = self.scroll_area.viewport().size()
        available_width = max(viewport_size.width() - 40, 100)
        available_height = max(viewport_size.height() - 40, 100)
        
        if self.zoom_mode == self.ZOOM_FIT:
            # Fit to window
            scaled = self.current_pixmap.scaled(
                available_width,
                available_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.zoom_level = scaled.width() / self.current_pixmap.width()
        elif self.zoom_mode == self.ZOOM_ACTUAL:
            # Actual size (100%)
            self.zoom_level = 1.0
            scaled = self.current_pixmap
        else:
            # Custom zoom
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
        self.zoom_mode = self.ZOOM_CUSTOM
        self.zoom_mode_combo.setCurrentText('Custom')
        self.zoom_level = min(self.zoom_level * 1.25, 5.0)
        self._update_display()
        self._update_info()
    
    def zoom_out(self):
        """Zoom out by 25%."""
        self.zoom_mode = self.ZOOM_CUSTOM
        self.zoom_mode_combo.setCurrentText('Custom')
        self.zoom_level = max(self.zoom_level / 1.25, 0.1)
        self._update_display()
        self._update_info()
    
    def reset_zoom(self):
        """Reset zoom to fit window."""
        self.zoom_mode = self.ZOOM_FIT
        self.zoom_mode_combo.setCurrentText('Fit to Window')
        self._update_display()
        self._update_info()
    
    def _on_zoom_mode_changed(self, mode_text: str):
        """Handle zoom mode selection change."""
        mode_map = {
            'Fit to Window': self.ZOOM_FIT,
            'Actual Size': self.ZOOM_ACTUAL,
            'Custom': self.ZOOM_CUSTOM
        }
        self.zoom_mode = mode_map.get(mode_text, self.ZOOM_FIT)
        
        if self.zoom_mode == self.ZOOM_ACTUAL:
            self.zoom_level = 1.0
        elif self.zoom_mode == self.ZOOM_FIT:
            self.zoom_level = 1.0  # Will be recalculated in _update_display
        
        self._update_display()
        self._update_info()
        self.zoom_mode_changed.emit(self.zoom_mode)
    
    def _update_info(self):
        """Update the info label."""
        if self.current_pixmap:
            mode_text = {
                self.ZOOM_FIT: "Fit",
                self.ZOOM_ACTUAL: "100%",
                self.ZOOM_CUSTOM: f"{int(self.zoom_level * 100)}%"
            }.get(self.zoom_mode, f"{int(self.zoom_level * 100)}%")
            
            self.info_label.setText(
                f"{self.current_pixmap.width()}x{self.current_pixmap.height()} | "
                f"Zoom: {mode_text}"
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
        if self.current_pixmap and self.zoom_mode == self.ZOOM_FIT:
            self._update_display()
    
    def clear(self):
        """Clear the current image."""
        self.current_pixmap = None
        self.current_file_path = None
        self.image_label.clear()
        self.info_label.setText("No image loaded")
    
    def _open_image_file(self):
        """Open the current image file in the default application."""
        if self.current_file_path and os.path.exists(self.current_file_path):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(self.current_file_path)
                elif os.name == 'posix':  # Linux/macOS
                    # Use Popen with stdout/stderr redirected to suppress portal warnings
                    subprocess.Popen(
                        ['xdg-open', self.current_file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
            except Exception as e:
                print(f"[ERROR] Failed to open image file: {e}")
        else:
            print("[DEBUG] No image file to open")
    
    def _open_containing_folder(self):
        """Open the folder containing the current image."""
        if self.current_file_path:
            folder_path = os.path.dirname(self.current_file_path)
            if os.path.exists(folder_path):
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(folder_path)
                    elif os.name == 'posix':  # Linux/macOS
                        # Use Popen with stdout/stderr redirected to suppress portal warnings
                        subprocess.Popen(
                            ['xdg-open', folder_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True
                        )
                except Exception as e:
                    print(f"[ERROR] Failed to open folder: {e}")
        else:
            print("[DEBUG] No folder to open")
