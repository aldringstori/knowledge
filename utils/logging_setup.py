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

# File handler for main.log
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "main.log"),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Create and configure Qdrant logger
qdrant_logger = logging.getLogger("qdrant")
qdrant_logger.setLevel(logging.DEBUG)
qdrant_logger.propagate = False  # Don't propagate to root logger

qdrant_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "qdrant.log"),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
qdrant_handler.setLevel(logging.DEBUG)
qdrant_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
qdrant_handler.setFormatter(qdrant_formatter)
qdrant_logger.addHandler(qdrant_handler)

# Create and configure Data Treatment logger
data_treatment_logger = logging.getLogger("data_treatment")
data_treatment_logger.setLevel(logging.DEBUG)
data_treatment_logger.propagate = False  # Don't propagate to root logger

data_treatment_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "data_treatment.log"),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
data_treatment_handler.setLevel(logging.DEBUG)
data_treatment_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
data_treatment_handler.setFormatter(data_treatment_formatter)
data_treatment_logger.addHandler(data_treatment_handler)


# Helper functions to get specific loggers
def get_qdrant_logger():
    return qdrant_logger


def get_data_treatment_logger():
    return data_treatment_logger


def get_session_logs(session_id=None, max_lines=100):
    """
    Get logs for a specific session or the most recent logs

    Args:
        session_id: Optional session ID to filter logs
        max_lines: Maximum number of lines to return

    Returns:
        List of log lines
    """
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


def read_log_file(log_file, max_lines=None):
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


def clear_log_file(log_file):
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


def clear_session_logs(session_id):
    """
    Clear the logs for a specific session

    Args:
        session_id: Session ID to clear logs for

    Returns:
        bool: True if successful, False otherwise
    """
    session_log = os.path.join(LOG_DIR, f"session_{session_id}.log")

    if not os.path.exists(session_log):
        logger.warning(f"Session log file for session {session_id} doesn't exist")
        return False

    return clear_log_file(f"session_{session_id}.log")