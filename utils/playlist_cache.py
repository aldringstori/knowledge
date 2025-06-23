import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Tuple
from utils.logging_setup import get_playlist_logger

logger = get_playlist_logger()

class PlaylistCache:
    """Cache system for playlist URLs and video metadata"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def _get_playlist_hash(self, playlist_url: str) -> str:
        """Generate a unique hash for a playlist URL"""
        return hashlib.md5(playlist_url.encode()).hexdigest()
    
    def _get_cache_file_path(self, playlist_url: str) -> str:
        """Get the cache file path for a playlist"""
        playlist_hash = self._get_playlist_hash(playlist_url)
        return os.path.join(self.cache_dir, f"playlist_{playlist_hash}.json")
    
    def load_cached_playlist(self, playlist_url: str) -> Dict:
        """Load cached playlist data if it exists"""
        cache_file = self._get_cache_file_path(playlist_url)
        
        if not os.path.exists(cache_file):
            logger.info(f"No cache found for playlist: {playlist_url}")
            return {}
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                logger.info(f"Loaded cache for playlist with {len(cached_data.get('videos', []))} videos")
                return cached_data
        except Exception as e:
            logger.error(f"Error loading cache file {cache_file}: {e}")
            return {}
    
    def save_playlist_cache(self, playlist_url: str, playlist_title: str, videos: List[Dict]) -> None:
        """Save playlist data to cache"""
        cache_file = self._get_cache_file_path(playlist_url)
        
        cache_data = {
            "playlist_url": playlist_url,
            "playlist_title": playlist_title,
            "last_fetched": datetime.now().isoformat(),
            "total_videos": len(videos),
            "videos": videos
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved cache for playlist '{playlist_title}' with {len(videos)} videos")
        except Exception as e:
            logger.error(f"Error saving cache file {cache_file}: {e}")
    
    def detect_changes(self, playlist_url: str, current_videos: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Compare current videos with cached videos to detect changes
        
        Returns:
            Tuple of (new_videos, existing_videos, removed_videos)
        """
        cached_data = self.load_cached_playlist(playlist_url)
        cached_videos = cached_data.get('videos', [])
        
        # Create sets of video IDs for comparison
        cached_video_ids = {video['id'] for video in cached_videos}
        current_video_ids = {video['id'] for video in current_videos}
        
        # Find new, existing, and removed videos
        new_video_ids = current_video_ids - cached_video_ids
        existing_video_ids = current_video_ids & cached_video_ids
        removed_video_ids = cached_video_ids - current_video_ids
        
        # Create lists of video objects
        new_videos = [video for video in current_videos if video['id'] in new_video_ids]
        existing_videos = [video for video in current_videos if video['id'] in existing_video_ids]
        removed_videos = [video for video in cached_videos if video['id'] in removed_video_ids]
        
        logger.info(f"Change detection results:")
        logger.info(f"  - New videos: {len(new_videos)}")
        logger.info(f"  - Existing videos: {len(existing_videos)}")
        logger.info(f"  - Removed videos: {len(removed_videos)}")
        
        return new_videos, existing_videos, removed_videos
    
    def get_processed_videos(self, playlist_url: str, output_path: str) -> Set[str]:
        """
        Get list of video IDs that have already been processed (have transcript files)
        
        Args:
            playlist_url: The playlist URL
            output_path: Path to the playlist output directory
        
        Returns:
            Set of video IDs that have been processed
        """
        processed_videos = set()
        
        if not os.path.exists(output_path):
            return processed_videos
        
        # Check for existing transcript files
        for filename in os.listdir(output_path):
            if filename.endswith('.txt') and filename != 'video_urls.txt':
                # Try to extract video ID from filename or check if file exists
                processed_videos.add(filename)
        
        logger.info(f"Found {len(processed_videos)} already processed videos in {output_path}")
        return processed_videos
    
    def filter_unprocessed_videos(self, videos: List[Dict], output_path: str) -> List[Dict]:
        """
        Filter out videos that have already been processed
        
        Args:
            videos: List of video dictionaries
            output_path: Path to check for existing files
        
        Returns:
            List of videos that haven't been processed yet
        """
        if not os.path.exists(output_path):
            return videos
        
        # Get list of existing transcript files
        existing_files = set()
        for filename in os.listdir(output_path):
            if filename.endswith('.txt') and filename != 'video_urls.txt':
                existing_files.add(filename)
        
        unprocessed_videos = []
        for video in videos:
            # Create expected filename for this video
            expected_filename = f"{video['title']}.txt"
            
            if expected_filename not in existing_files:
                unprocessed_videos.append(video)
            else:
                logger.debug(f"Skipping already processed video: {video['title']}")
        
        logger.info(f"Filtered to {len(unprocessed_videos)} unprocessed videos out of {len(videos)} total")
        return unprocessed_videos
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache"""
        cache_files = [f for f in os.listdir(self.cache_dir) if f.startswith('playlist_') and f.endswith('.json')]
        
        total_playlists = len(cache_files)
        total_videos = 0
        oldest_cache = None
        newest_cache = None
        
        for cache_file in cache_files:
            try:
                with open(os.path.join(self.cache_dir, cache_file), 'r') as f:
                    data = json.load(f)
                    total_videos += data.get('total_videos', 0)
                    
                    last_fetched = data.get('last_fetched')
                    if last_fetched:
                        if oldest_cache is None or last_fetched < oldest_cache:
                            oldest_cache = last_fetched
                        if newest_cache is None or last_fetched > newest_cache:
                            newest_cache = last_fetched
            except Exception:
                continue
        
        return {
            'total_playlists': total_playlists,
            'total_videos': total_videos,
            'oldest_cache': oldest_cache,
            'newest_cache': newest_cache
        }
    
    def clear_cache(self, playlist_url: str = None) -> bool:
        """
        Clear cache for a specific playlist or all playlists
        
        Args:
            playlist_url: If provided, clear only this playlist's cache
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if playlist_url:
                # Clear specific playlist cache
                cache_file = self._get_cache_file_path(playlist_url)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    logger.info(f"Cleared cache for playlist: {playlist_url}")
                else:
                    logger.info(f"No cache found for playlist: {playlist_url}")
            else:
                # Clear all cache files
                cache_files = [f for f in os.listdir(self.cache_dir) if f.startswith('playlist_') and f.endswith('.json')]
                for cache_file in cache_files:
                    os.remove(os.path.join(self.cache_dir, cache_file))
                logger.info(f"Cleared all playlist caches ({len(cache_files)} files)")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False