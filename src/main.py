"""Entry point for the SD Image Viewer application."""
import sys
import os
import argparse

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.core.metadata_cache import MetadataCache
from src.core.thumbnail_persistence import ThumbnailPersistence


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="SD Image Viewer - A viewer for Stable Diffusion generated images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                    Start the application normally
  python -m src.main --reset            Clear all caches and start fresh
  python -m src.main --reset --no-confirm  Clear caches without confirmation
  python -m src.main --folder /path/to/images  Open a specific folder on startup
        """
    )
    
    parser.add_argument(
        '--reset', '--clear-db',
        action='store_true',
        dest='reset',
        help='Clear all caches (metadata, thumbnails) and rebuild from scratch'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        dest='no_confirm',
        help='Skip confirmation dialog when using --reset'
    )
    
    parser.add_argument(
        '--folder', '-f',
        type=str,
        dest='folder',
        help='Open a specific folder on startup'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser.parse_args()


def clear_all_caches(no_confirm: bool = False) -> bool:
    """
    Clear all application caches.
    
    Args:
        no_confirm: If True, skip confirmation dialog
        
    Returns:
        True if caches were cleared, False if cancelled
    """
    # Show confirmation dialog unless --no-confirm is set
    if not no_confirm:
        # Need a temporary QApplication for the dialog
        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication([])
        
        reply = QMessageBox.question(
            None,
            "Confirm Reset",
            "This will clear all cached data:\n\n"
            "• Metadata cache (JSON files)\n"
            "• Thumbnail cache (disk thumbnails)\n"
            "• Image index (in-memory, rebuilt on folder load)\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            print("Reset cancelled by user.")
            return False
    
    print("Clearing all caches...")
    
    # Clear metadata cache
    try:
        metadata_cache = MetadataCache()
        if metadata_cache.clear_cache():
            print("  ✓ Metadata cache cleared")
        else:
            print("  ✗ Failed to clear metadata cache")
    except Exception as e:
        print(f"  ✗ Error clearing metadata cache: {e}")
    
    # Clear thumbnail cache
    try:
        thumbnail_persistence = ThumbnailPersistence()
        count = thumbnail_persistence.clear_cache()
        print(f"  ✓ Thumbnail cache cleared ({count} files removed)")
    except Exception as e:
        print(f"  ✗ Error clearing thumbnail cache: {e}")
    
    print("Cache reset complete. The image index will be rebuilt when you open a folder.")
    return True


def main():
    """Main entry point."""
    # Parse command-line arguments
    args = parse_args()
    
    # Handle --reset flag before creating the main application
    if args.reset:
        if not clear_all_caches(args.no_confirm):
            # User cancelled, exit
            sys.exit(0)
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SD Image Viewer")
    app.setApplicationVersion("1.0.0")
    
    # Set application-wide font
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Open folder if specified
    if args.folder:
        if os.path.isdir(args.folder):
            window.load_folder(args.folder)
        else:
            QMessageBox.warning(
                window,
                "Invalid Folder",
                f"The specified folder does not exist:\n{args.folder}"
            )
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
