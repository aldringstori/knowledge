"""
SQLite database utility for tracking downloaded video transcriptions.
Prevents duplicate downloads by storing video URLs and metadata.
"""

import sqlite3
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from utils.logging_setup import get_module_logger

logger = get_module_logger("video_database")


class VideoDatabase:
    """Database manager for tracking downloaded video transcriptions"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection and create tables if needed
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Try to use data directory, with fallback to /tmp
            try:
                data_dir = os.path.join(os.getcwd(), "data")
                if not os.path.exists(data_dir):
                    os.makedirs(data_dir, exist_ok=True)
                db_path = os.path.join(data_dir, "video_downloads.db")
            except PermissionError:
                # Fallback to tmp directory
                db_path = "/tmp/video_downloads.db"
                logger.warning(f"Using fallback database path: {db_path}")
        
        self.db_path = db_path
        self._init_database()
        logger.info(f"Video database initialized at: {self.db_path}")
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create videos table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS downloaded_videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        video_url TEXT NOT NULL,
                        video_id TEXT NOT NULL,
                        url_hash TEXT UNIQUE NOT NULL,
                        title TEXT,
                        duration TEXT,
                        file_path TEXT,
                        file_size INTEGER,
                        download_timestamp DATETIME NOT NULL,
                        source_type TEXT DEFAULT 'single',
                        source_url TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index for faster lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_url_hash ON downloaded_videos(url_hash)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_video_id ON downloaded_videos(video_id)
                ''')
                
                conn.commit()
                logger.info("Database tables created/verified successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _generate_url_hash(self, video_url: str) -> str:
        """Generate a unique hash for the video URL"""
        return hashlib.sha256(video_url.encode('utf-8')).hexdigest()[:16]
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from YouTube URL"""
        import re
        # Handle various YouTube URL formats
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/shorts/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        
        # If no match, use the URL hash as ID
        return self._generate_url_hash(video_url)
    
    def is_video_downloaded(self, video_url: str) -> bool:
        """
        Check if a video has already been downloaded
        
        Args:
            video_url: YouTube video URL to check
            
        Returns:
            True if video was already downloaded, False otherwise
        """
        try:
            url_hash = self._generate_url_hash(video_url)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM downloaded_videos WHERE url_hash = ?',
                    (url_hash,)
                )
                count = cursor.fetchone()[0]
                
                is_downloaded = count > 0
                if is_downloaded:
                    logger.info(f"Video already downloaded: {video_url}")
                else:
                    logger.debug(f"Video not in database: {video_url}")
                
                return is_downloaded
                
        except Exception as e:
            logger.error(f"Error checking if video is downloaded: {e}")
            return False
    
    def add_downloaded_video(self, video_url: str, title: str = None, 
                           file_path: str = None, duration: str = None,
                           source_type: str = 'single', source_url: str = None) -> bool:
        """
        Add a downloaded video to the database
        
        Args:
            video_url: YouTube video URL
            title: Video title
            file_path: Path to the downloaded transcript file
            duration: Video duration
            source_type: Type of source ('single', 'playlist', 'channel')
            source_url: Original source URL (playlist/channel URL)
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            video_id = self._extract_video_id(video_url)
            url_hash = self._generate_url_hash(video_url)
            file_size = None
            
            # Get file size if file path is provided
            if file_path and os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                except:
                    pass
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Use INSERT OR REPLACE to handle potential duplicates
                cursor.execute('''
                    INSERT OR REPLACE INTO downloaded_videos 
                    (video_url, video_id, url_hash, title, duration, file_path, 
                     file_size, download_timestamp, source_type, source_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video_url, video_id, url_hash, title, duration, file_path,
                    file_size, datetime.now(), source_type, source_url, datetime.now()
                ))
                
                conn.commit()
                logger.info(f"Added video to database: {title or video_url}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding video to database: {e}")
            return False
    
    def get_downloaded_video(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a downloaded video
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Dictionary with video information or None if not found
        """
        try:
            url_hash = self._generate_url_hash(video_url)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                cursor = conn.cursor()
                
                cursor.execute(
                    'SELECT * FROM downloaded_videos WHERE url_hash = ?',
                    (url_hash,)
                )
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def get_all_downloaded_videos(self, source_type: str = None) -> List[Dict[str, Any]]:
        """
        Get list of all downloaded videos
        
        Args:
            source_type: Filter by source type ('single', 'playlist', 'channel')
            
        Returns:
            List of dictionaries with video information
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if source_type:
                    cursor.execute(
                        'SELECT * FROM downloaded_videos WHERE source_type = ? ORDER BY download_timestamp DESC',
                        (source_type,)
                    )
                else:
                    cursor.execute(
                        'SELECT * FROM downloaded_videos ORDER BY download_timestamp DESC'
                    )
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting all videos: {e}")
            return []
    
    def remove_video(self, video_url: str) -> bool:
        """
        Remove a video from the database
        
        Args:
            video_url: YouTube video URL to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            url_hash = self._generate_url_hash(video_url)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM downloaded_videos WHERE url_hash = ?',
                    (url_hash,)
                )
                
                rows_affected = cursor.rowcount
                conn.commit()
                
                if rows_affected > 0:
                    logger.info(f"Removed video from database: {video_url}")
                    return True
                else:
                    logger.warning(f"Video not found in database: {video_url}")
                    return False
                
        except Exception as e:
            logger.error(f"Error removing video from database: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total videos
                cursor.execute('SELECT COUNT(*) FROM downloaded_videos')
                total_videos = cursor.fetchone()[0]
                
                # Videos by source type
                cursor.execute('''
                    SELECT source_type, COUNT(*) as count 
                    FROM downloaded_videos 
                    GROUP BY source_type
                ''')
                by_source = dict(cursor.fetchall())
                
                # Total file size
                cursor.execute('SELECT SUM(file_size) FROM downloaded_videos WHERE file_size IS NOT NULL')
                total_size = cursor.fetchone()[0] or 0
                
                # Latest download
                cursor.execute('SELECT MAX(download_timestamp) FROM downloaded_videos')
                latest_download = cursor.fetchone()[0]
                
                return {
                    'total_videos': total_videos,
                    'by_source_type': by_source,
                    'total_file_size': total_size,
                    'latest_download': latest_download,
                    'database_path': self.db_path
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def cleanup_orphaned_entries(self) -> int:
        """
        Remove database entries where the transcript file no longer exists
        
        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all entries with file paths
                cursor.execute('SELECT id, file_path FROM downloaded_videos WHERE file_path IS NOT NULL')
                entries = cursor.fetchall()
                
                orphaned_ids = []
                for entry_id, file_path in entries:
                    if not os.path.exists(file_path):
                        orphaned_ids.append(entry_id)
                
                # Remove orphaned entries
                if orphaned_ids:
                    placeholders = ','.join('?' * len(orphaned_ids))
                    cursor.execute(f'DELETE FROM downloaded_videos WHERE id IN ({placeholders})', orphaned_ids)
                    conn.commit()
                    
                    logger.info(f"Removed {len(orphaned_ids)} orphaned database entries")
                
                return len(orphaned_ids)
                
        except Exception as e:
            logger.error(f"Error cleaning up orphaned entries: {e}")
            return 0


# Global database instance
_video_db_instance = None


def get_video_database() -> VideoDatabase:
    """Get global video database instance (singleton pattern)"""
    global _video_db_instance
    if _video_db_instance is None:
        _video_db_instance = VideoDatabase()
    return _video_db_instance


def is_video_already_downloaded(video_url: str) -> bool:
    """
    Convenience function to check if a video was already downloaded
    
    Args:
        video_url: YouTube video URL
        
    Returns:
        True if video was already downloaded, False otherwise
    """
    db = get_video_database()
    return db.is_video_downloaded(video_url)


def mark_video_as_downloaded(video_url: str, title: str = None, 
                           file_path: str = None, duration: str = None,
                           source_type: str = 'single', source_url: str = None) -> bool:
    """
    Convenience function to mark a video as downloaded
    
    Args:
        video_url: YouTube video URL
        title: Video title
        file_path: Path to the downloaded transcript file
        duration: Video duration
        source_type: Type of source ('single', 'playlist', 'channel')
        source_url: Original source URL (playlist/channel URL)
        
    Returns:
        True if marked successfully, False otherwise
    """
    db = get_video_database()
    return db.add_downloaded_video(video_url, title, file_path, duration, source_type, source_url)