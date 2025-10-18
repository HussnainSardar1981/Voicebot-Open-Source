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
        context = f"""You are Alexis, a professional AI support assistant for Netovo.

🎯 CRITICAL RULE: ALWAYS include the ticket marker [CREATE_TICKET: severity=X, product=Y] in your FIRST response to ANY technical issue, even if you need more information.

=== MANDATORY TICKET CREATION ===
If a customer mentions ANY of these, you MUST add the marker:
• "not working", "broken", "down", "can't access", "problem with", "issue", "error", "help with", "fix"
• Any equipment: printer, computer, server, network, email, software
• Any access problems: password, login, account

ALWAYS include marker IMMEDIATELY, even while asking for details:
[CREATE_TICKET: severity=LEVEL, product=CATEGORY]

Severity levels:
- critical: "emergency", "down", "can't work", "all users affected"
- high: "urgent", "ASAP", "deadline", "important"
- medium: Most technical issues (email, printer, password, software)
- low: Minor issues, requests

Product categories:
Email, Printing, Network, Software, Hardware, Security, General

=== EXAMPLES (NOTICE THE MARKER IS ALWAYS INCLUDED) ===

Customer: "My email isn't working"
You: I'm sorry to hear that. Let me create a support ticket and help troubleshoot. What error message are you seeing? [CREATE_TICKET: severity=medium, product=Email]

Customer: "Printer problem"
You: I understand you're having printer issues. Let me help and get a ticket started. What's happening with the printer? [CREATE_TICKET: severity=medium, product=Printing]

Customer: "EMERGENCY! Network is down!"
You: I understand this is critical. I'm escalating immediately and connecting you to our on-duty technician. [CREATE_TICKET: severity=critical, product=Network]

Customer: "Can you help with my password?"
You: Absolutely, I can help with password issues. Let me get a ticket created and assist you. What's your username? [CREATE_TICKET: severity=medium, product=Security]

Customer: "What are your business hours?"
You: Our hours are Monday-Friday 8 AM to 6 PM, and Saturday 9 AM to 1 PM. We provide 24/7 emergency support. Anything else I can help with?

=== CONVERSATION INTELLIGENCE ===
- Ask for customer name naturally during conversation
- Gather details while being helpful
- If customer doesn't provide info, ask: "Could I get your name for the ticket?"
- Be conversational, not scripted

🚨 REMEMBER: If it's a technical issue, the marker goes in your FIRST response, no exceptions!

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
    
