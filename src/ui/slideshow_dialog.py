"""Slideshow settings and control dialog."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QCheckBox, QSlider, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class SlideshowDialog(QDialog):
    """Dialog for slideshow settings and control."""
    
    # Signals
    start_slideshow = pyqtSignal(int, bool)  # interval_ms, random_order
    stop_slideshow = pyqtSignal()
    next_image = pyqtSignal()
    previous_image = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_playing = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        
        self.setWindowTitle("Slideshow")
        self.setModal(False)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Interval setting
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" seconds")
        self.interval_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                padding: 5px;
            }
        """)
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        settings_layout.addLayout(interval_layout)
        
        # Random order checkbox
        self.random_check = QCheckBox("Random order")
        self.random_check.setStyleSheet("color: #eee;")
        settings_layout.addWidget(self.random_check)
        
        # Loop checkbox
        self.loop_check = QCheckBox("Loop slideshow")
        self.loop_check.setChecked(True)
        self.loop_check.setStyleSheet("color: #eee;")
        settings_layout.addWidget(self.loop_check)
        
        layout.addWidget(settings_group)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.previous_image.emit)
        controls_layout.addWidget(self.prev_btn)
        
        self.play_btn = QPushButton("▶ Start")
        self.play_btn.clicked.connect(self._toggle_slideshow)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        controls_layout.addWidget(self.play_btn)
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_image.emit)
        controls_layout.addWidget(self.next_btn)
        
        layout.addLayout(controls_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)
        
        # Set dialog style
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
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2a2a2a;
                border: 1px solid #444;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border: 1px solid #4a9eff;
            }
        """)
        
        self.setFixedWidth(300)
    
    def _toggle_slideshow(self):
        """Toggle slideshow on/off."""
        if self.is_playing:
            self._stop_slideshow()
        else:
            self._start_slideshow()
    
    def _start_slideshow(self):
        """Start the slideshow."""
        self.is_playing = True
        self.play_btn.setText("⏸ Pause")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffaa4a;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #ffbb5a;
            }
        """)
        
        # Disable settings during playback
        self.interval_spin.setEnabled(False)
        self.random_check.setEnabled(False)
        
        # Start timer
        interval_ms = self.interval_spin.value() * 1000
        self.timer.start(interval_ms)
        
        # Emit signal
        self.start_slideshow.emit(interval_ms, self.random_check.isChecked())
    
    def _stop_slideshow(self):
        """Stop the slideshow."""
        self.is_playing = False
        self.play_btn.setText("▶ Start")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        
        # Re-enable settings
        self.interval_spin.setEnabled(True)
        self.random_check.setEnabled(True)
        
        # Stop timer
        self.timer.stop()
        
        # Emit signal
        self.stop_slideshow.emit()
    
    def _on_timer(self):
        """Handle timer timeout - advance to next image."""
        self.next_image.emit()
    
    def closeEvent(self, event):
        """Handle dialog close - stop slideshow."""
        if self.is_playing:
            self._stop_slideshow()
        event.accept()
    
    def keyPressEvent(self, event):
        """Handle key presses for manual control."""
        from PyQt6.QtCore import Qt
        
        if event.key() == Qt.Key.Key_Left:
            self.previous_image.emit()
        elif event.key() == Qt.Key.Key_Right:
            self.next_image.emit()
        elif event.key() == Qt.Key.Key_Space:
            self._toggle_slideshow()
        else:
            super().keyPressEvent(event)
