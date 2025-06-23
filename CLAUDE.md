# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment (required for all operations)
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env file to customize settings
```

### Running the Application
```bash
# Start the Streamlit application
streamlit run knowledge.py

# Run with specific port
streamlit run knowledge.py --server.port 8501
```

### Development & Testing
```bash
# Check Python syntax
python -m py_compile knowledge.py

# Test imports and basic functionality
python -c "from modules import single_video; print('Imports working')"

# Check Selenium WebDriver setup
python -c "from utils.common import setup_selenium_driver; driver = setup_selenium_driver(); print('Driver:', type(driver)); driver.quit() if driver else None"
```

## Architecture Overview

### Core Architecture Pattern
This is a **modular Streamlit application** with a **plugin-style architecture** where each YouTube content type has its own processing module. The system uses a **dual-API approach** (YouTube Transcript API + Selenium fallback) for robust transcript extraction.

### Critical Architectural Components

**1. URL Type Detection & Routing (`knowledge.py`)**
- `detect_url_type()` determines content type from URL patterns
- Routes to appropriate module based on URL type (video/short/playlist/channel)
- Each module exposes a `render_url(url, config)` function

**2. Selenium WebDriver Architecture (`utils/common.py`)**
- **Driver Hierarchy**: Edge (primary) → Chrome (fallback) 
- **Non-headless mode**: Browser visible for debugging transcript extraction issues
- **Retry mechanism**: 3 attempts with randomized delays for anti-bot resilience

**3. Progress Tracking System (`utils/table_utils.py`)**
- **Real-time updates**: Streamlit session state + pandas DataFrame 
- **Dual-status tracking**: URL fetched ✅/❌ + Video downloaded ✅/❌
- **Process isolation**: Each item tracked individually with detailed error reporting

**4. Configuration Management (`utils/config.py`)**
- **Environment-based config**: All settings loaded from `.env` file using python-dotenv
- **Type-safe loading**: Automatic conversion of environment variables to appropriate types (bool, int, float, list)
- **GPU configuration**: Selenium GPU acceleration controlled via `SELENIUM_USE_GPU=true/false`
- **Folder management**: Auto-creation of output directories per content type

### Data Flow Architecture

1. **URL Input** → `detect_url_type()` → **Module Router**
2. **Module Processing**:
   - Playlist/Channel: Uses Selenium to extract video URLs
   - Individual items: Direct transcript extraction
3. **Transcript Extraction**:
   - Primary: YouTube Transcript API (via `youtube_transcript_api`)
   - Fallback: Selenium web scraping with multiple selectors
4. **Progress Display**: Real-time table updates via `table_utils.py`
5. **Output**: Text files in `transcriptions/` with sanitized filenames

### Module Interface Contract

All processing modules must implement:
```python
def render_url(url: str, config: dict) -> None:
    """
    Process a URL and handle transcript extraction
    
    Args:
        url: YouTube URL to process
        config: Contains 'download_folder', 'name_extractor', 'api_handler'
    """
```

### Compatibility Layer
- **Import patches** (`huggingface_patch.py`, `transformers_patch.py`): Applied before module imports
- **Monkey patching**: Addresses version incompatibilities in dependencies
- **Must be imported first**: Critical for avoiding import errors

### Error Handling Strategy
- **Graceful degradation**: Multiple fallback mechanisms at each level
- **Detailed logging**: Comprehensive error tracking via `utils/logging_setup.py`
- **User feedback**: Streamlit UI shows progress and errors in real-time
- **Retry logic**: Built into Selenium operations with exponential backoff

### Browser Automation Specifics
- **Visible browser**: Headless mode disabled for debugging
- **Dynamic content loading**: Scroll-based video discovery for playlists
- **Anti-detection**: Random delays and realistic user-agent strings
- **Multi-selector approach**: Multiple CSS selectors for transcript buttons/panels

## Configuration Management

### Environment Variables (.env)
All configuration is now managed through environment variables in the `.env` file:

**Key Settings:**
- `SELENIUM_USE_GPU=true/false` - Enable/disable GPU acceleration for Selenium
- `SELENIUM_HEADLESS_MODE=true/false` - Default headless mode (overridden by UI toggle)
- `BROWSER_PREFERENCE=edge/chrome` - Primary browser choice
- `MAX_TRANSCRIPT_RETRIES=3` - Number of retry attempts for failed transcripts
- `DOWNLOAD_FOLDER=transcriptions` - Output directory for saved transcripts

**Configuration Loading:**
- All settings loaded via `utils/config.py` using python-dotenv
- Type-safe conversion (bool, int, float, list) with sensible defaults
- No more JSON configuration files

## Key Implementation Notes

### WebDriver Management
Always use `setup_selenium_driver()` from `utils/common.py` - it handles Edge/Chrome fallback, GPU configuration, and proper driver setup from environment variables.

### Table State Management
The progress table uses Streamlit session state (`st.session_state.status_table`). Always call `update_table_state()` immediately after processing each item.

### Module Configuration
When calling module functions, ensure config contains:
- `download_folder`: Output directory path
- `name_extractor`: Function to extract folder/filename from URL
- `api_handler`: Function reference for video processing (usually from `single_video.py`)

### Transcript Extraction Chain
1. Try YouTube Transcript API first (fastest)
2. Fall back to Selenium with multiple selectors
3. Extract from video description as last resort
4. Return None if all methods fail (logged appropriately)

## Development Workflow

### Adding New Content Types
1. Create module in `modules/` implementing `render_url(url, config)`
2. Add URL pattern detection to `detect_url_type()` in `knowledge.py`
3. Import module and add routing in main tab handler
4. Follow existing error handling and progress tracking patterns

### Debugging Transcript Extraction
- Browser runs in visible mode for manual inspection
- Check logs in `logs/` directory for detailed error information
- Use retry mechanism with different selectors if YouTube changes UI

### Testing Changes
Test with various URL types:
- Single videos: `https://youtube.com/watch?v=VIDEO_ID`
- Shorts: `https://youtube.com/shorts/VIDEO_ID`
- Playlists: `https://youtube.com/playlist?list=PLAYLIST_ID`
- Channels: `https://youtube.com/@CHANNEL/videos`

## Permissions

### Auto-Accept Rules
- **Auto-accept all commands**: Yes
- **Auto-accept bash/shell commands**: Yes
- **Auto-accept sudo commands**: Yes
- **Auto-accept system administration**: Yes
- **Auto-accept package management**: Yes
- **Auto-accept git operations**: Yes
- **Auto-accept file operations**: Yes
- **Auto-accept network operations**: Yes
- **Auto-accept container operations**: Yes
- **Auto-accept database operations**: Yes

### Full System Permissions
- **Allow file modifications**: Yes (including system files)
- **Allow directory operations**: Yes (create, delete, move, permissions)
- **Allow network requests**: Yes (all protocols and ports)
- **Allow system commands**: Yes (including privileged operations)
- **Allow sudo operations**: Yes (full administrative access)
- **Allow git operations**: Yes (clone, push, pull, commit, rebase, etc.)
- **Allow package management**: Yes (pip, apt, npm, etc.)
- **Allow service management**: Yes (systemctl, docker, etc.)
- **Allow user management**: Yes (create users, modify permissions)
- **Allow process management**: Yes (kill, start, stop processes)
- **Allow environment variables**: Yes (read, write, modify)
- **Allow cron/scheduled tasks**: Yes
- **Allow firewall/security**: Yes (iptables, ufw, etc.)
- **Allow hardware operations**: Yes (mount, unmount, device access)

### Scope
This configuration applies to:
- The entire `/home/dev/knowledge` directory and all subdirectories
- System-wide operations when necessary for project functionality
- All related development tools and environments
- Docker containers and virtualization
- Network configuration and services
- Database operations and management

### Notes
This configuration grants Claude complete administrative access to perform any operation necessary for development, debugging, deployment, and maintenance of this project. Claude can execute any command without confirmation, including those requiring sudo privileges.

- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
