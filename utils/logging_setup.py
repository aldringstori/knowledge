import logging
from io import StringIO

# Configure logging to an external file
logging.basicConfig(
    filename='knowledge.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StringIOHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.stream = StringIO()

    def emit(self, record):
        msg = self.format(record)
        self.stream.write(msg + '\n')

    def get_contents(self):
        return self.stream.getvalue()

    def clear(self):
        self.stream = StringIO()

# Create a string handler for the current session logs
string_handler = StringIOHandler()
string_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(string_handler)

def read_log_file(filename='knowledge.log', last_n_lines=100):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return ''.join(lines[-last_n_lines:])
    except Exception as e:
        return f"Error reading log file: {str(e)}"

def clear_log_file(filename='knowledge.log'):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('')
        return True
    except Exception as e:
        logger.error(f"Error clearing log file: {str(e)}")
        return False

def get_session_logs():
    return string_handler.get_contents()

def clear_session_logs():
    string_handler.clear()