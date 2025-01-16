from .chat_ui import ChatUI

def render(config):
    """Entry point for the chat module"""
    chat_ui = ChatUI(config)
    chat_ui.render()