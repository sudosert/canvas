# SD Image Viewer

A desktop image viewer application tailored for Stable Diffusion generated images. It supports metadata extraction from A1111 and ComfyUI outputs, with advanced prompt-based filtering, fullscreen viewing, and slideshow modes.

## Features

- **Metadata Extraction**: Automatically reads generation parameters from PNG and JPEG files
  - Supports A1111 (Automatic1111) format
  - Supports ComfyUI format
  - Extracts prompts, negative prompts, models, seeds, and more

- **Prompt Filtering**: Advanced filtering system
  - Include terms: Show only images containing ALL specified terms
  - Exclude terms: Hide images containing ANY specified terms
  - Real-time filtering as you type
  - Case-insensitive substring matching

- **Multiple View Modes**:
  - Thumbnail grid for browsing
  - Single image view with zoom support
  - Fullscreen mode (F11)
  - Slideshow with configurable timing

- **Keyboard Navigation**:
  - Arrow keys: Previous/Next image
  - F11: Toggle fullscreen
  - F5: Open slideshow controls
  - Ctrl++ / Ctrl+-: Zoom in/out
  - Ctrl+0: Reset zoom
  - Escape: Exit fullscreen

## Installation

### Requirements
- Python 3.8 or higher
- PyQt6
- Pillow

### Setup

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Application

#### Using the Launcher Scripts (Recommended)

The launcher scripts automatically handle virtual environment creation and dependency installation:

**Linux/macOS:**
```bash
./launch.sh
```

**Windows:**
```cmd
launch.bat
```

The launcher will:
1. Create a `.venv` virtual environment if it doesn't exist
2. Install/update requirements from `requirements.txt` if needed
3. Launch the application

You can also pass command-line arguments:
```bash
./launch.sh --reset --folder /path/to/images
```

#### Manual Launch

If you prefer to run manually:

```bash
python src/main.py
```

### Command-Line Options

```bash
# Show help
python src/main.py --help

# Clear all caches and start fresh (with confirmation dialog)
python src/main.py --reset

# Clear all caches without confirmation
python src/main.py --reset --no-confirm

# Open a specific folder on startup
python src/main.py --folder /path/to/images

# Combine options
python src/main.py --reset --no-confirm --folder /path/to/images
```

| Option | Description |
|--------|-------------|
| `--reset`, `--clear-db` | Clear all caches (metadata, thumbnails) and rebuild from scratch |
| `--no-confirm` | Skip confirmation dialog when using `--reset` |
| `--folder`, `-f` | Open a specific folder on startup |
| `--version`, `-v` | Show version number |
| `--help`, `-h` | Show help message |

### Opening Images

1. Click "Open Folder" or press Ctrl+O
2. Select a folder containing your Stable Diffusion images
3. The application will scan for PNG and JPEG files and extract metadata

### Filtering Images

- **Include**: Enter terms separated by commas to show only images containing ALL terms
  - Example: `blue sky, clouds` shows images with both "blue sky" AND "clouds"
  
- **Exclude**: Enter terms separated by commas to hide images containing ANY term
  - Example: `nsfw, blurry` hides images with "nsfw" OR "blurry"

### Viewing Images

- Click any thumbnail to view it in the main viewer
- Use mouse wheel + Ctrl to zoom in/out
- Double-click or press F11 for fullscreen
- Use left/right arrow keys to navigate

### Slideshow

1. Press F5 or click "Slideshow" to open controls
2. Set the interval (1-60 seconds)
3. Optionally enable random order
4. Click "Start" to begin

### Copying Prompts

In the metadata panel on the right:
- Click "Copy Prompt" to copy the positive prompt
- Click "Copy Negative Prompt" to copy the negative prompt

## Supported Metadata Formats

### A1111 (Automatic1111)
Reads from PNG text chunk `parameters`:
```
Prompt text here
Negative prompt: negative text here
Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: 12345, Size: 512x768, Model: model-name
```

### ComfyUI
Reads from PNG text chunks `workflow` and `prompt`:
- Extracts prompts from CLIPTextEncode nodes
- Reads generation parameters from KSampler nodes
- Captures model information from CheckpointLoader nodes

## Project Structure

```
sd-image-viewer/
├── src/
│   ├── main.py                      # Application entry point with CLI
│   ├── models/
│   │   └── image_data.py            # Image metadata dataclass
│   ├── core/
│   │   ├── metadata_parser.py       # A1111/ComfyUI metadata extraction
│   │   ├── image_scanner.py         # Directory scanning
│   │   ├── image_index.py           # SQLite index for filtering
│   │   ├── metadata_cache.py        # JSON metadata caching
│   │   ├── thumbnail_persistence.py # Disk thumbnail cache
│   │   ├── image_storage.py         # SQLite BLOB storage
│   │   └── postgres_image_storage.py # PostgreSQL large object storage
│   ├── ui/
│   │   ├── main_window.py           # Main application window
│   │   ├── thumbnail_grid.py        # Basic thumbnail browser
│   │   ├── paginated_thumbnail_grid.py # Paginated thumbnail browser
│   │   ├── image_viewer.py          # Single image view
│   │   ├── metadata_panel.py        # Metadata display
│   │   ├── filter_bar.py            # Filter controls
│   │   ├── slideshow_dialog.py      # Slideshow controls
│   │   └── image_storage_dialog.py  # Storage management UI
│   └── utils/
│       └── image_cache.py           # Memory thumbnail cache
├── docs/
│   └── database-recommendations.md  # Scaling recommendations
├── launch.sh                        # Linux/macOS launcher script
├── launch.bat                       # Windows launcher script
├── requirements.txt
└── README.md
```

## License

MIT License - Feel free to use and modify as needed.
