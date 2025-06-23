import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_env_bool(key, default=False):
    """Get boolean value from environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(key, default=0):
    """Get integer value from environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_float(key, default=0.0):
    """Get float value from environment variable"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_list(key, default=None, separator=','):
    """Get list value from environment variable"""
    if default is None:
        default = []
    value = os.getenv(key, '')
    if not value:
        return default
    return [item.strip() for item in value.split(separator)]

def get_config():
    """Load configuration from environment variables"""
    # Force reload of environment variables
    load_dotenv(override=True)
    
    # Debug print
    print(f"DEBUG: DOWNLOAD_FOLDER env var = {os.getenv('DOWNLOAD_FOLDER', 'NOT_SET')}")
    print(f"DEBUG: Current working directory = {os.getcwd()}")
    
    config = {
        # Application settings
        'app_port': get_env_int('APP_PORT', 8501),
        'app_host': os.getenv('APP_HOST', '0.0.0.0'),
        
        # Directories
        'download_folder': os.getenv('DOWNLOAD_FOLDER', 'transcriptions'),
        'transcription_folder': os.getenv('TRANSCRIPTION_FOLDER', 'transcriptions'),
        'model_path': os.getenv('MODEL_PATH', 'models'),
        'qdrant_path': os.getenv('QDRANT_PATH', 'qdrant_data'),
        
        # Selenium Configuration
        'selenium_use_gpu': get_env_bool('SELENIUM_USE_GPU', True),
        'headless_mode': get_env_bool('SELENIUM_HEADLESS_MODE', False),
        'selenium_window_size': os.getenv('SELENIUM_WINDOW_SIZE', '1920,1080'),
        'selenium_user_agent': os.getenv('SELENIUM_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        
        # YouTube Class Names (dynamically updated)
        'youtube_show_more_button_class': os.getenv('YOUTUBE_SHOW_MORE_BUTTON_CLASS', '//tp-yt-paper-button[@id="expand"]'),
        'youtube_show_transcript_button_class': os.getenv('YOUTUBE_SHOW_TRANSCRIPT_BUTTON_CLASS', '//button[contains(text(), "Show transcript")]'),
        'youtube_transcript_panel_class': os.getenv('YOUTUBE_TRANSCRIPT_PANEL_CLASS', 'ytd-transcript-search-panel-renderer'),
        'youtube_transcript_segments_class': os.getenv('YOUTUBE_TRANSCRIPT_SEGMENTS_CLASS', 'yt-formatted-string.segment-text'),
        'youtube_video_title_class': os.getenv('YOUTUBE_VIDEO_TITLE_CLASS', 'span.style-scope.yt-formatted-string'),
        
        # Playlist Selectors
        'youtube_playlist_container_class': os.getenv('YOUTUBE_PLAYLIST_CONTAINER_CLASS', 'ytd-playlist-video-list-renderer'),
        'youtube_playlist_video_renderer_class': os.getenv('YOUTUBE_PLAYLIST_VIDEO_RENDERER_CLASS', 'ytd-playlist-video-renderer'),
        'youtube_playlist_video_title_id': os.getenv('YOUTUBE_PLAYLIST_VIDEO_TITLE_ID', 'video-title'),
        'youtube_playlist_fallback_container_class': os.getenv('YOUTUBE_PLAYLIST_FALLBACK_CONTAINER_CLASS', 'ytd-playlist-panel-video-renderer'),
        
        # Browser Preferences
        'browser_preference': os.getenv('BROWSER_PREFERENCE', 'edge'),
        'browser_retry_attempts': get_env_int('BROWSER_RETRY_ATTEMPTS', 3),
        'browser_retry_delay_min': get_env_float('BROWSER_RETRY_DELAY_MIN', 2.0),
        'browser_retry_delay_max': get_env_float('BROWSER_RETRY_DELAY_MAX', 5.0),
        
        # Transcript Settings
        'max_transcript_retries': get_env_int('MAX_TRANSCRIPT_RETRIES', 3),
        'transcript_languages': get_env_list('TRANSCRIPT_LANGUAGES', ['en', 'es', 'fr', 'de', 'pt', 'it']),
        'auto_translate_to_english': get_env_bool('AUTO_TRANSLATE_TO_ENGLISH', True),
        
        # Claude Configuration
        'claude': {
            'auto_accept': {
                'all_commands': get_env_bool('CLAUDE_AUTO_ACCEPT_ALL_COMMANDS', True),
                'file_operations': get_env_bool('CLAUDE_AUTO_ACCEPT_FILE_OPERATIONS', True),
                'directory_operations': get_env_bool('CLAUDE_AUTO_ACCEPT_DIRECTORY_OPERATIONS', True),
                'network_requests': get_env_bool('CLAUDE_AUTO_ACCEPT_NETWORK_REQUESTS', True),
                'system_commands': get_env_bool('CLAUDE_AUTO_ACCEPT_SYSTEM_COMMANDS', True),
                'git_operations': get_env_bool('CLAUDE_AUTO_ACCEPT_GIT_OPERATIONS', True),
                'package_management': get_env_bool('CLAUDE_AUTO_ACCEPT_PACKAGE_MANAGEMENT', True),
            },
            'permissions': {
                'full_access': get_env_bool('CLAUDE_FULL_ACCESS', True),
                'require_confirmation': get_env_bool('CLAUDE_REQUIRE_CONFIRMATION', False),
            }
        },
        
        # Logging Configuration
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_file': os.getenv('LOG_FILE', 'logs/main.log'),
        'log_max_size': os.getenv('LOG_MAX_SIZE', '10MB'),
        'log_backup_count': get_env_int('LOG_BACKUP_COUNT', 5),
        
        # Performance Settings
        'enable_caching': get_env_bool('ENABLE_CACHING', True),
        'cache_ttl': get_env_int('CACHE_TTL', 3600),
        'max_concurrent_downloads': get_env_int('MAX_CONCURRENT_DOWNLOADS', 3),
        'download_delay_seconds': get_env_int('DOWNLOAD_DELAY_SECONDS', 3),
    }
    
    return config

def save_config(config):
    """Save configuration - now handled via environment variables"""
    # Since we're using environment variables, we don't need to save to a file
    # This function is kept for backward compatibility
    pass

def update_config(key, value):
    """Update configuration - now handled via environment variables"""
    # Since we're using environment variables, updates should be made to .env file
    # This function is kept for backward compatibility
    pass

def delete_files():
    """Placeholder for delete_files function"""
    return True, "Files deleted successfully"


def get_transcript_files():
    """Placeholder for get_transcript_files function"""
    config = get_config()
    folder = config.get('download_folder', '')
    if not os.path.exists(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.txt')]