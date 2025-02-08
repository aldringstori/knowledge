# File: ./modules/chat/context_processor.py
from typing import List, Dict, Tuple, Set, Optional  # Added typing imports
from utils.logging_setup import logger
import os
from datetime import datetime


class ContextProcessor:
    def __init__(self):
        self.context_cache = {}
        self.relevance_threshold = 0.7

    def process_search_results(self, results: List[Dict], query: str) -> Tuple[List[str], Set[str]]:
        """Process and enhance search results"""
        try:
            context_texts = []
            sources = set()
            scores = []

            for result in results:
                # Skip if below threshold
                if result['score'] < self.relevance_threshold:
                    continue

                text = result['payload']['text']
                source = os.path.basename(result['payload']['source'])
                score = result['score']

                # Add to collections
                context_texts.append(text)
                sources.add(source)
                scores.append(score)

                # Cache this context
                cache_key = f"{query}_{source}"
                self.context_cache[cache_key] = {
                    'text': text,
                    'score': score,
                    'timestamp': datetime.now()
                }

            return context_texts, sources

        except Exception as e:
            logger.error(f"Error processing search results: {str(e)}")
            return [], set()

    def format_context(self, context_texts: List[str], max_length: int = 1500) -> str:
        """Format context for prompt"""
        try:
            # Join contexts with clear separators
            formatted = "\n---\n".join(context_texts)

            # Trim to max length while preserving word boundaries
            if len(formatted) > max_length:
                formatted = formatted[:max_length].rsplit(' ', 1)[0] + '...'

            return formatted

        except Exception as e:
            logger.error(f"Error formatting context: {str(e)}")
            return ""

    def enhance_prompt(self,
                       query: str,
                       context_texts: List[str],
                       chat_history: str = "") -> str:
        """Create enhanced prompt with context and history"""
        try:
            context = self.format_context(context_texts)

            prompt = f"""Based on the following transcript content and conversation history,
please provide a detailed and relevant answer.

Context:
{context}

Previous conversation:
{chat_history}

Question: {query}

Please provide a clear and informative answer based on the given context."""

            return prompt

        except Exception as e:
            logger.error(f"Error creating enhanced prompt: {str(e)}")
            return query