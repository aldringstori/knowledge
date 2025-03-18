# File: ./modules/chat/__init__.py
from .chat_ui import ChatUI
from .rag_manager import RAGManager
from .model_manager import ModelManager
from .chat_history import ChatHistory
from .context_processor import ContextProcessor

def render(config):
    """Initialize and render chat interface"""
    chat_ui = ChatUI(config)
    chat_ui.render()