# YouTube Class Updater

This script automatically detects and updates YouTube's dynamic class names and selectors for transcript extraction.

## Features

- **Auto-detection**: Finds current working selectors for YouTube transcript elements
- **Multi-step process**: Handles the complete transcript extraction workflow
- **Environment integration**: Updates `.env` file with working selectors
- **Flexible selectors**: Supports both CSS and XPath selectors
- **Anti-detection**: Uses realistic browser behavior to avoid YouTube's anti-bot measures
- **Multi-language support**: Works with different YouTube language interfaces

## Usage

### Basic Usage
```bash
# Activate virtual environment
source venv/bin/activate

# Run with default settings (will prompt for URL)
python update_youtube_classes.py

# Run with specific video URL
python update_youtube_classes.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Interactive Mode
```bash
python update_youtube_classes.py
# Will prompt for:
# - YouTube video URL (or use default)
# - Headless mode preference (y/n)
```

## How It Works

### Step 1: Show More Button
Finds and clicks the "Show more" button to expand video description:
- Looks for `tp-yt-paper-button[@id="expand"]`
- Fallback to text-based selectors: "...mais", "Show more", "...more"

### Step 2: Show Transcript Button  
Finds and clicks the "Show transcript" button:
- Supports multiple languages: "Show transcript", "Mostrar transcrição"
- Uses XPath text matching for reliability
- Updates `YOUTUBE_SHOW_TRANSCRIPT_BUTTON_CLASS` in .env

### Step 3: Transcript Panel
Waits for transcript panel to appear:
- Detects `ytd-transcript-search-panel-renderer`
- Updates `YOUTUBE_TRANSCRIPT_PANEL_CLASS` in .env

### Step 4: Extract Transcript Segments
Extracts text from transcript segments:
- Finds `yt-formatted-string.segment-text` elements
- Extracts `textContent` from each segment
- Updates `YOUTUBE_TRANSCRIPT_SEGMENTS_CLASS` in .env

## Environment Variables Updated

The script updates these variables in your `.env` file:

```bash
# YouTube Class Names (updated dynamically)
YOUTUBE_SHOW_MORE_BUTTON_CLASS=//tp-yt-paper-button[@id="expand"]
YOUTUBE_SHOW_TRANSCRIPT_BUTTON_CLASS=//button[contains(text(), "Show transcript")]
YOUTUBE_TRANSCRIPT_PANEL_CLASS=ytd-transcript-search-panel-renderer
YOUTUBE_TRANSCRIPT_SEGMENTS_CLASS=yt-formatted-string.segment-text
```

## Integration with Main Application

The main transcript extraction in `utils/common.py` automatically uses these updated selectors:

1. **Dynamic Selector Loading**: Reads current selectors from .env
2. **Fallback Mechanism**: Uses default selectors if .env values fail
3. **Multi-selector Support**: Tries multiple selectors in priority order

## Anti-Detection Features

- **Realistic User Agent**: Mimics real browser
- **Random Delays**: Human-like timing between actions
- **Webdriver Property Removal**: Hides automation from JavaScript detection
- **Scroll Behavior**: Scrolls to elements before clicking
- **JavaScript Clicking**: Uses `execute_script` for reliable clicking

## Logging

The script creates detailed logs in `youtube_class_updater.log`:

- Element detection attempts
- Successful selector matches
- Click actions and timing
- Error conditions and fallbacks
- Environment variable updates

## Troubleshooting

### Common Issues

1. **Element Not Found**
   - YouTube may have changed their interface
   - Try running in non-headless mode to see what's happening
   - Check the log file for specific error details

2. **Click Failures**
   - Elements may be covered by other UI elements
   - Try different video URLs (some have different layouts)
   - Increase delays between actions

3. **Transcript Not Available**
   - Not all videos have transcripts
   - Some videos have auto-generated captions only
   - Try with different video types (longer videos often have transcripts)

### Debug Mode
```bash
# Run in visible browser mode for debugging
python update_youtube_classes.py
# Choose 'n' for headless mode to see browser actions
```

## Best Practices

1. **Regular Updates**: Run this script periodically to keep selectors current
2. **Test Videos**: Use videos you know have transcripts for testing
3. **Backup .env**: Keep a backup of working .env configurations
4. **Monitor Logs**: Check logs when transcript extraction starts failing

## Example Output

```
✅ Update completed successfully! Check the .env file for updated selectors.

2024-01-15 10:30:15 - INFO - Chrome WebDriver setup successful
2024-01-15 10:30:18 - INFO - Page loaded successfully  
2024-01-15 10:30:19 - INFO - Found show more button using: //tp-yt-paper-button[@id="expand"]
2024-01-15 10:30:21 - INFO - Found show transcript button using: //button[contains(text(), "Show transcript")]
2024-01-15 10:30:24 - INFO - Found transcript panel using: ytd-transcript-search-panel-renderer
2024-01-15 10:30:25 - INFO - Found 156 transcript segments using: yt-formatted-string.segment-text
2024-01-15 10:30:25 - INFO - Successfully extracted transcript with 156 segments
```