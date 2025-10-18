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

    def generate(self, prompt, max_tokens=150):
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

=== INTELLIGENT TICKET CREATION ===
When customers have technical issues, you need to gather information naturally through conversation and then create a ticket.

TICKET CREATION RULES:
- For ANY technical problem, add [CREATE_TICKET: severity=X, product=Y] at the END of your response
- Choose severity intelligently: critical (system down/emergency), high (urgent business impact), medium (standard issues), low (minor issues)
- Choose product intelligently: Email, Printing, Network, Software, Hardware, Security, or General

INTELLIGENT INFORMATION GATHERING:
- If customer hasn't given their name, ask naturally during conversation
- If problem isn't clear, ask follow-up questions to understand the issue
- If you need more details (severity, product type), ask conversationally
- Be helpful and professional, not robotic

SMART EXAMPLES:

Customer: "My printer won't work"
Response: I'm sorry to hear about your printer trouble. To help you better, could I get your name? Also, what exactly happens when you try to print - does it show any error messages? [CREATE_TICKET: severity=medium, product=Printing]

Customer: "Hi, I'm Sarah from accounting. Our entire email system is down!"
Response: Hi Sarah, that sounds critical. I'm creating an urgent ticket right away. Are all users affected or just some? I'll get our technicians on this immediately. [CREATE_TICKET: severity=critical, product=Email]

Customer: "John here, having some software issues"
Response: Hi John, I'd be happy to help with your software issue. Can you tell me which software is giving you trouble and what specifically is happening? [CREATE_TICKET: severity=medium, product=Software]

Customer: "What are your business hours?"
Response: Our hours are Monday-Friday 8 AM to 6 PM, and Saturday 9 AM to 1 PM. We provide 24/7 emergency support for critical issues. Is there anything else I can help you with?

BE CONVERSATIONAL AND INTELLIGENT - don't ask for everything at once, gather information naturally through the conversation flow.

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
    
