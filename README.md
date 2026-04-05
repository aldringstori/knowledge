# YouTube Transcript Assistant

An open source software made with Python and Streamlit to download transcriptions from YouTube videos, YouTube shorts, and playlists.

## Features
| ✨ Features              | Implemented|                         Description                                       |
| -----------------------  | -----------| ------------------------------------------------------------------------- |
| Individual videos        |     ✅     | Single youtube video transcription download                               |
| Individual shorts        |     ✅     | Single youtube shorts transcription download                              |
| Massive channel          |     ✅     | Bulk/Massive Youtube channel all videos                                   |
| Massive shorts           |     ✅     | All shorts from a channel transcriptions download                         |
| Playlists                |     ✅     | All transcriptions from a playlist transcriptions download                |
| Queue multiple channels  |     ✅     | Put multiple channels into a queue for download                           |
| Convert pdf books to txt |     ✅     | Convert pdfs or entire books to txt                                       | 
| Ingest and chat RAG      |     ✅     | Convert pdfs or entire books to txt                                       | 
| Convert text files to different formats
| Progress tracking with visual table showing URL fetching and download status
| Automatic retry mechanism for failed downloads
| Support for multiple languages with automatic translation to English

## Project Structure

```
knowledge/
├── knowledge.py              # Main application entry point
├── requirements.txt         # Python dependencies
├── settings.json           # Application settings
├── modules/                # Core functionality modules
│   ├── single_video.py     # Single video processing
│   ├── single_short.py     # Single short processing
│   ├── playlist.py         # Playlist processing
│   ├── channel_videos.py   # Channel video processing
│   ├── channel_shorts.py   # Channel shorts processing
│   ├── file_converter.py   # File format conversion
│   └── summarize.py        # Transcript summarization (disabled)
├── utils/                  # Utility functions
│   ├── common.py           # Common utilities and transcript fetching
│   ├── config.py           # Configuration management
│   ├── logging_setup.py    # Logging configuration
│   └── table_utils.py      # Progress table utilities
├── logs/                   # Application logs
├── transcriptions/         # Downloaded transcripts (created automatically)
├── venv/                   # Python virtual environment
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
└── *.py                   # Compatibility patches
```

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `streamlit run knowledge.py`

## Usage

1. Start the application with `streamlit run knowledge.py`
2. Navigate to the "Download" tab
3. Enter a YouTube URL (video, short, playlist, or channel)
4. Click "Process and Download"
5. Monitor progress in the visual table with checkmarks
6. Find downloaded transcripts in the `transcriptions/` folder

## YouTube Class Updater

If transcript extraction starts failing due to YouTube interface changes, run the class updater:

```bash
python update_youtube_classes.py
```

This script automatically detects and updates YouTube's dynamic class names for reliable transcript extraction. See `YOUTUBE_CLASS_UPDATER.md` for detailed usage instructions.

## Browser Support

The application uses Selenium WebDriver and supports:
- Microsoft Edge (primary)
- Google Chrome (fallback)
- Visible browser mode for debugging (headless mode disabled)

## Note

This application uses YouTube's transcript API and web scraping. Some videos may fail due to YouTube's anti-bot measures or missing captions. The app includes automatic retry mechanisms and supports multiple languages.
