# File: ./modules/chat/chat_history.py
from typing import List, Dict, Optional  # Added typing imports
from datetime import datetime
from utils.logging_setup import logger


class ChatHistory:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.messages = []
        self.chat_contexts = {}  # Store context for each conversation turn

    def add_message(self, role: str, content: str, context: List[str] = None):
        """Add a message to history with optional context"""
        try:
            message_id = len(self.messages)
            timestamp = datetime.now().isoformat()

            message = {
                'id': message_id,
                'role': role,
                'content': content,
                'timestamp': timestamp
            }

            self.messages.append(message)

            if context:
                self.chat_contexts[message_id] = context

            # Trim history if needed
            if len(self.messages) > self.max_history:
                removed_id = self.messages.pop(0)['id']
                self.chat_contexts.pop(removed_id, None)

        except Exception as e:
            logger.error(f"Error adding message to history: {str(e)}")

    def get_recent_context(self, num_messages: int = 3) -> str:
        """Get recent conversation context"""
        try:
            recent = self.messages[-num_messages:] if self.messages else []
            context = []

            for msg in recent:
                msg_context = f"{msg['role']}: {msg['content']}"
                if msg['id'] in self.chat_contexts:
                    msg_context += f"\nContext: {' '.join(self.chat_contexts[msg['id']])}"
                context.append(msg_context)

            return "\n".join(context)

        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return ""

    def clear_history(self):
        """Clear chat history"""
        self.messages = []
        self.chat_contexts = {}