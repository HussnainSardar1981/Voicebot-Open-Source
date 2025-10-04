#!/usr/bin/env python3
"""
SimpleOllamaClient - AI Conversation handling using Ollama
Extracted from production_agi_voicebot.py
"""

import logging

logger = logging.getLogger(__name__)

class SimpleOllamaClient:
    """Enhanced Ollama client with robust conversation context"""

    def __init__(self):
        self.conversation_history = []
        self.greeting_given = False
        self.current_topic = None
        self.topic_keywords = []
        self.conversation_summary = ""

    def generate(self, prompt, max_tokens=50):
        """Generate response with enhanced conversation context"""
        try:
            import httpx

            # Simple conversation tracking
            # No complex topic extraction needed

            # Simple, effective conversation context
            context = """You are Alexis, a helpful NETOVO customer support assistant.

You are helping a customer with their technical question. Listen to what they say and help them solve their specific problem. Keep responses short and conversational.

"""

            if not self.greeting_given:
                context += "You already introduced yourself.\n"
                self.greeting_given = True

            # Add recent conversation history (simple format)
            if self.conversation_history:
                context += "\nRecent conversation:\n"
                for entry in self.conversation_history[-3:]:
                    context += f"Human: {entry['user']}\nAssistant: {entry['bot']}\n"

            context += f"\nHuman: {prompt}\nAssistant:"

            payload = {
                "model": "orca2:7b",
                "prompt": context,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.4,  # Moderate temperature for consistency
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                    "stop": ["\nHuman:", "\nUser:", "Human:", "User:"]
                }
            }

            with httpx.Client(timeout=15.0) as client:
                response = client.post("http://localhost:11434/api/generate", json=payload)
                response.raise_for_status()

                result = response.json()
                text = result.get("response", "").strip()

                # Validate and clean up the response
                text = self._validate_and_clean_response(text, prompt)

                # Store in conversation history
                self.conversation_history.append({
                    "user": prompt,
                    "bot": text
                })

                # Simple memory management
                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-8:]

                logger.info(f"Ollama response: {text[:50]}")
                return text

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "I'm having technical difficulties. How else can I help?"

    def _validate_and_clean_response(self, text, user_input):
        """Validate response relevance and clean up artifacts"""
        if not text:
            return "I'm sorry, could you please repeat that?"

        # Remove common artifacts
        text = text.replace("Some possible responses are:", "")
        text = text.replace("Assistant:", "")
        text = text.replace("Human:", "")
        text = text.replace("You:", "")
        text = text.replace("Customer:", "")

        # Split by lines and take the first meaningful response
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            for line in lines:
                if len(line) > 10 and not line.startswith('-') and not line.startswith('*'):
                    text = line
                    break

        # Simple validation - only catch obviously wrong responses
        text_lower = text.lower()

        # Only block completely irrelevant responses
        if "thank you for uploading" in text_lower and "upload" not in user_input.lower():
            return "How can I help you with that?"

        # Block other obviously wrong responses
        if any(phrase in text_lower for phrase in ["some possible responses are", "i don't understand what you mean by filename"]):
            return "Could you tell me more about the issue you're experiencing?"

        return text.strip()