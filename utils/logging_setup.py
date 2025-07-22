import os
import logging
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clear existing handlers to avoid duplicates
if logger.handlers:
    logger.handlers.clear()

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler for main.log (with error handling)
try:
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "main.log"),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except PermissionError:
    # If we can't write to the log file, just use console logging
    print("Warning: Cannot write to log file due to permissions. Using console logging only.")
    pass

# Create and configure Qdrant logger
qdrant_logger = logging.getLogger("qdrant")
qdrant_logger.setLevel(logging.DEBUG)
qdrant_logger.propagate = False  # Don't propagate to root logger

try:
    qdrant_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "qdrant.log"),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    qdrant_handler.setLevel(logging.DEBUG)
    qdrant_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    qdrant_handler.setFormatter(qdrant_formatter)
    qdrant_logger.addHandler(qdrant_handler)
except PermissionError:
    # If we can't write to the log file, just use console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter('[QDRANT] %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    qdrant_logger.addHandler(console_handler)

# Create and configure Data Treatment logger
data_treatment_logger = logging.getLogger("data_treatment")
data_treatment_logger.setLevel(logging.DEBUG)
data_treatment_logger.propagate = False  # Don't propagate to root logger

try:
    data_treatment_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "data_treatment.log"),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    data_treatment_handler.setLevel(logging.DEBUG)
    data_treatment_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    data_treatment_handler.setFormatter(data_treatment_formatter)
    data_treatment_logger.addHandler(data_treatment_handler)
except PermissionError:
    # If we can't write to the log file, just use console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter('[DATA_TREATMENT] %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    data_treatment_logger.addHandler(console_handler)


# Module-specific loggers
module_loggers = {}

def setup_logger(module_name):
    """
    Setup and return a logger for the given module name.
    This is an alias for get_module_logger for backward compatibility.
    
    Args:
        module_name: Name of the module
    
    Returns:
        Logger instance for the module
    """
    return get_module_logger(module_name)

def get_module_logger(module_name):
    """
    Get or create a module-specific logger
    
    Args:
        module_name: Name of the module (e.g., 'playlist', 'single_video')
    
    Returns:
        Logger instance for the module
    """
    if module_name not in module_loggers:
        # Create new module logger
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.DEBUG)
        module_logger.propagate = False  # Don't propagate to root logger
        
        # Create file handler for this module (with error handling)
        try:
            module_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, f"{module_name}.log"),
                maxBytes=10485760,  # 10MB
                backupCount=5
            )
            module_handler.setLevel(logging.DEBUG)
            module_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            module_handler.setFormatter(module_formatter)
            module_logger.addHandler(module_handler)
        except PermissionError:
            # If we can't write to the log file, skip file handler
            pass
        
        # Also add console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(f'[{module_name.upper()}] %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        module_logger.addHandler(console_handler)
        
        module_loggers[module_name] = module_logger
    
    return module_loggers[module_name]

# Helper functions to get specific loggers
def get_qdrant_logger():
    return qdrant_logger

def get_data_treatment_logger():
    return data_treatment_logger

def get_playlist_logger():
    return get_module_logger('playlist')

def get_single_video_logger():
    return get_module_logger('single_video')

def get_single_short_logger():
    return get_module_logger('single_short')

def get_channel_videos_logger():
    return get_module_logger('channel_videos')

def get_channel_shorts_logger():
    return get_module_logger('channel_shorts')

def get_file_converter_logger():
    return get_module_logger('file_converter')

def get_summarize_logger():
    return get_module_logger('summarize')


def get_session_logs(session_id=None, max_lines=100):
    """
    Get logs for a specific session or the most recent logs

    Args:
        session_id: Optional session ID to filter logs
        max_lines: Maximum number of lines to return

    Returns:
        List of log lines
    """
    # Get all log files in the logs directory
    log_files = []
    try:
        for file in os.listdir(LOG_DIR):
            if file.endswith('.log'):
                log_files.append(os.path.join(LOG_DIR, file))
    except Exception:
        # Fallback to known log files
        log_files = [
            os.path.join(LOG_DIR, "main.log"),
            os.path.join(LOG_DIR, "qdrant.log"),
            os.path.join(LOG_DIR, "data_treatment.log")
        ]

    # Only include files that exist
    log_files = [f for f in log_files if os.path.exists(f)]

    # If session_id provided, look for session-specific log
    if session_id:
        session_log = os.path.join(LOG_DIR, f"session_{session_id}.log")
        if os.path.exists(session_log):
            log_files = [session_log]

    # Collect recent logs from all applicable files
    all_logs = []

    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                logs = f.readlines()

                # Add file identifier to each line
                file_name = os.path.basename(log_file)
                logs = [f"[{file_name}] {line}" for line in logs]

                all_logs.extend(logs)
        except Exception as e:
            all_logs.append(f"Error reading {log_file}: {str(e)}\n")

    # Return the most recent logs up to max_lines
    return all_logs[-max_lines:] if all_logs else []


def read_log_file(log_file="main.log", max_lines=None):
    """
    Read a log file and return its contents

    Args:
        log_file: Name of the log file in the logs directory (e.g., "main.log")
        max_lines: Maximum number of lines to return (None for all lines)

    Returns:
        List of log lines or empty list if file not found
    """
    file_path = os.path.join(LOG_DIR, log_file)

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r') as f:
            if max_lines:
                # Read last N lines efficiently
                lines = []
                for line in reversed(f.readlines()):
                    lines.append(line)
                    if len(lines) >= max_lines:
                        break
                return list(reversed(lines))
            else:
                # Read all lines
                return f.readlines()
    except Exception as e:
        return [f"Error reading log file: {str(e)}\n"]


def clear_log_file(log_file="main.log"):
    """
    Clear the contents of a log file

    Args:
        log_file: Name of the log file in the logs directory (e.g., "main.log")

    Returns:
        bool: True if successful, False otherwise
    """
    file_path = os.path.join(LOG_DIR, log_file)

    try:
        # Open the file in write mode, which clears its contents
        with open(file_path, 'w') as f:
            f.write(
                f"Log file cleared at {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, None, None, None))}\n")
        return True
    except Exception as e:
        logger.error(f"Error clearing log file {log_file}: {str(e)}")
        return False


def clear_session_logs(session_id=None):
    """
    Clear the logs for a specific session or all session logs
    
    Args:
        session_id: Session ID to clear logs for (None to clear all session logs)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if session_id is None:
        # Clear all session logs
        try:
            for file in os.listdir(LOG_DIR):
                if file.startswith('session_') and file.endswith('.log'):
                    os.remove(os.path.join(LOG_DIR, file))
            return True
        except Exception as e:
            logger.error(f"Error clearing session logs: {str(e)}")
            return False
    
    # Clear specific session log
    session_log = os.path.join(LOG_DIR, f"session_{session_id}.log")

    if not os.path.exists(session_log):
        logger.warning(f"Session log file for session {session_id} doesn't exist")
        return False

    return clear_log_file(f"session_{session_id}.log")