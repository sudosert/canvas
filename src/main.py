"""Entry point for the SD Image Viewer application."""
import sys
import os
import argparse

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer

from src.ui.main_window import MainWindow
from src.ui.splash_screen import SplashScreen
from src.core.metadata_cache import MetadataCache
from src.core.thumbnail_persistence import ThumbnailPersistence
from src.core.image_storage import ImageStorage
from src.core.postgres_image_storage import PostgresImageStorage, POSTGRES_AVAILABLE


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
  python -m src.main --skip-db-update   Skip database update, use existing data
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
        '--skip-db-update',
        action='store_true',
        dest='skip_db_update',
        help='Skip database update/refresh, use existing data only'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser.parse_args()


def _print_progress(step: int, total: int, message: str):
    """Print a progress indicator for the reset process."""
    progress = int((step / total) * 100)
    bar_width = 30
    filled = int((step / total) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"\r  [{bar}] {progress:3d}% - {message}", end="", flush=True)
    if step == total:
        print()  # New line when complete


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
            "• Stored images (SQLite database)\n"
            "• PostgreSQL storage (if configured)\n"
            "• Image index (in-memory, rebuilt on folder load)\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            print("Reset cancelled by user.")
            return False
    
    print("Clearing all caches...")
    
    # Define total steps for progress tracking
    total_steps = 4  # Metadata, Thumbnails, SQLite, PostgreSQL check
    current_step = 0
    
    # Clear metadata cache
    current_step += 1
    _print_progress(current_step, total_steps, "Clearing metadata cache...")
    try:
        metadata_cache = MetadataCache()
        if metadata_cache.clear_cache():
            pass  # Progress already shown
        else:
            print("\n  ✗ Failed to clear metadata cache")
    except Exception as e:
        print(f"\n  ✗ Error clearing metadata cache: {e}")
    
    # Clear thumbnail cache
    current_step += 1
    _print_progress(current_step, total_steps, "Clearing thumbnail cache...")
    try:
        thumbnail_persistence = ThumbnailPersistence()
        count = thumbnail_persistence.clear_cache()
    except Exception as e:
        print(f"\n  ✗ Error clearing thumbnail cache: {e}")
    
    # Clear SQLite image storage
    current_step += 1
    _print_progress(current_step, total_steps, "Clearing SQLite storage...")
    try:
        image_storage = ImageStorage()
        if image_storage.clear_cache():
            pass  # Progress already shown
        else:
            print("\n  ✗ Failed to clear SQLite image storage")
        image_storage.close()
    except Exception as e:
        print(f"\n  ✗ Error clearing SQLite image storage: {e}")
    
    # Clear PostgreSQL storage if available
    current_step += 1
    _print_progress(current_step, total_steps, "Checking PostgreSQL...")
    if POSTGRES_AVAILABLE:
        try:
            # Build connection string from environment variables
            host = os.environ.get("POSTGRES_IP", "")
            user = os.environ.get("POSTGRES_USER", "")
            password = os.environ.get("POSTGRES_PASS", "")
            database = os.environ.get("POSTGRES_DB", "sd_images")
            port = os.environ.get("POSTGRES_PORT", "5432")
            
            if host and user and password:
                conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
                try:
                    postgres_storage = PostgresImageStorage(conn_string)
                    if postgres_storage.is_connected():
                        _print_progress(current_step, total_steps, "Clearing PostgreSQL...")
                        if postgres_storage.clear_all():
                            pass  # Success
                        else:
                            print("\n  ✗ Failed to clear PostgreSQL storage")
                    else:
                        _print_progress(current_step, total_steps, "PostgreSQL not connected")
                    postgres_storage.close()
                except Exception as conn_e:
                    _print_progress(current_step, total_steps, f"PostgreSQL: {conn_e}")
        except Exception as e:
            print(f"\n  ✗ Error clearing PostgreSQL storage: {e}")
    
    _print_progress(total_steps, total_steps, "Complete!")
    print("\nCache reset complete. The image index will be rebuilt when you open a folder.")
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
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    
    # Initialize components
    splash.update_status("Initializing application...")
    app.processEvents()
    
    # Create main window (but don't show yet)
    splash.update_status("Loading user interface...")
    app.processEvents()
    window = MainWindow(skip_db_update=args.skip_db_update)
    
    # Close splash and show main window
    def show_main_window():
        splash.finish(window)
        window.show()
        
        # Load folder after UI is shown
        if args.folder:
            if os.path.isdir(args.folder):
                # Use QTimer to load folder after event loop starts
                QTimer.singleShot(100, lambda: window._load_folder(args.folder))
            else:
                QMessageBox.warning(
                    window,
                    "Invalid Folder",
                    f"The specified folder does not exist:\n{args.folder}"
                )
        else:
            # Load last folder if no folder specified
            last_folder = window.settings.value("last_folder", "")
            if last_folder and os.path.isdir(last_folder):
                QTimer.singleShot(100, lambda: window._load_folder(last_folder))
    
    # Show main window after a short delay
    QTimer.singleShot(500, show_main_window)
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
