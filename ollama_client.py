#!/usr/bin/env python3
"""
SimpleOllamaClient - AI Conversation handling using Ollama
Extracted from production_agi_voicebot.py
"""

# ollama_client.py

import logging
import httpx
from config import MODEL_SETTINGS

logger = logging.getLogger(__name__)

class SimpleOllamaClient:
    """Enhanced Ollama client with robust conversation context"""

    def __init__(self, model_name="phi4"):
        self.model_name = model_name
        self.settings = MODEL_SETTINGS.get(model_name, MODEL_SETTINGS["phi4"])
        self.conversation_history = []
        self.greeting_given = False

    def generate(self, prompt, max_tokens=50):
        """Generate response with enhanced conversation context"""
        try:
            context = self._build_context(prompt)
            payload = {
                "model": self.settings["model"],
                "prompt": context,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": self.settings["temperature"],
                    "top_p": self.settings["top_p"],
                    "repeat_penalty": self.settings["repeat_penalty"],
                    "stop": self.settings["stop"]
                }
            }

            with httpx.Client(timeout=15.0) as client:
                response = client.post("http://localhost:11434/api/generate", json=payload)
                response.raise_for_status()
                result = response.json()
                text = result.get("response", "").strip()

                text = self._validate_and_clean_response(text, prompt)
                self.conversation_history.append({"user": prompt, "bot": text})

                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-8:]

                logger.info(f"Ollama response: {text[:50]}")
                return text

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "I'm having technical difficulties. How else can I help?"

    def _build_context(self, prompt):
        """Build the conversation context"""
        context = f"""You are Alexis, Netovo's professional AI support assistant.

=== TICKET CREATION PROTOCOL ===
When a customer describes a TECHNICAL ISSUE that needs follow-up:
- Include in your response: [CREATE_TICKET: urgency=<level>]
- Place marker at END of your response (so it's easy to remove)

Urgency Levels:
• critical - "emergency", "down", "entire network", "can't work", "all users affected"
• high - "urgent", "important", "ASAP", "deadline"
• medium - Standard technical issues (email, printer, password, access)
• low - Minor issues, feature requests

DO NOT create tickets for:
• Business hours, pricing, general info questions → Answer directly
• Billing/invoice questions → Answer directly
• Casual conversation → Respond naturally

=== EXAMPLES ===

Example 1 (Critical):
Customer: "EMERGENCY! Network is completely down!"
Response: I understand this is critical. I'm escalating immediately and connecting you to our on-duty technician. [CREATE_TICKET: urgency=critical]

Example 2 (Medium):
Customer: "My email stopped working"
Response: I'm sorry to hear that. Let me create a support ticket and help troubleshoot. What error message are you seeing? [CREATE_TICKET: urgency=medium]

Example 3 (No Ticket):
Customer: "What are your business hours?"
Response: Our hours are Monday-Friday 8 AM to 6 PM, and Saturday 9 AM to 1 PM. We provide 24/7 emergency support. Anything else I can help with?

Example 4 (No Ticket):
Customer: "Can I get a copy of my invoice?"
Response: I can help with that. Let me transfer you to our billing department who can send you a copy immediately.

You are helping a customer with their technical question. Listen to what they say and help them solve their specific problem. Keep responses short and conversational.

"""
        if not self.greeting_given:
            context += "You already introduced yourself.\n"
            self.greeting_given = True

        if self.conversation_history:
            context += "\nRecent conversation:\n"
            for entry in self.conversation_history[-3:]:
                context += f"Human: {entry['user']}\nAssistant: {entry['bot']}\n"

        context += f"\nHuman: {prompt}\nAssistant:"
        return context

    def _validate_and_clean_response(self, text, user_input):
        """Validate response relevance and clean up artifacts"""
        logger.debug(f"Cleaning response: {text[:20]}")
        if not text:
            return "I'm sorry, could you please repeat that?"

        text = text.replace("Some possible responses are:", "")
        text = text.replace("Assistant:", "")
        text = text.replace("Human:", "")
        text = text.replace("You:", "")
        text = text.replace("Customer:", "")

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            for line in lines:
                if len(line) > 10 and not line.startswith('-') and not line.startswith('*'):
                    text = line
                    break

        text_lower = text.lower()
        if "thank you for uploading" in text_lower and "upload" not in user_input.lower():
            return "How can I help you with that?"

        if any(phrase in text_lower for phrase in ["some possible responses are", "i don't understand what you mean by filename"]):
            return "Could you tell me more about the issue you're experiencing?"

        return text.strip()
