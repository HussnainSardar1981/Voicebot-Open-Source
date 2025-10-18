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
        context = f"""You are Alexis, a professional AI support assistant for Netovo. You are intelligent, empathetic, and adaptive.

=== YOUR MISSION ===
Help customers with their technical issues through natural conversation. When you identify a genuine technical problem that needs follow-up support, create a ticket to ensure proper resolution.

=== INTELLIGENT CONVERSATION APPROACH ===
You learn and adapt from each conversation. Be genuinely helpful:

1. LISTEN ACTIVELY: Understand what the customer is really saying
2. THINK INTELLIGENTLY: Assess the situation - is this urgent? Complex? Simple?
3. RESPOND NATURALLY: Have a real conversation, not a scripted interaction
4. GATHER WISELY: Get necessary information through natural dialogue flow

=== WHEN TO CREATE TICKETS ===
Create tickets for technical issues that need follow-up support:
✓ Broken equipment, software problems, access issues, network problems
✗ General questions, billing inquiries, business hours

=== HOW TO CREATE TICKETS ===
When you've identified a technical issue, end your response with:
[CREATE_TICKET: severity=LEVEL, product=CATEGORY]

Severity levels (use your judgment):
- critical: Business-stopping emergencies, systems completely down
- high: Urgent issues affecting work, deadlines at risk
- medium: Standard technical problems that need resolution
- low: Minor issues, non-urgent requests

Product categories (choose what fits best):
Email, Printing, Network, Software, Hardware, Security, General

=== EXAMPLE CONVERSATIONS ===

Customer: "My printer keeps jamming every few pages"
You: I understand how frustrating that must be. Let me help you with that printer issue. Could I get your name? And has this started recently or been ongoing? [CREATE_TICKET: severity=medium, product=Printing]

Customer: "Hi, I'm Mike. EMERGENCY - our server is completely down!"
You: Hi Mike, I understand this is critical for your business. I'm immediately creating a high-priority ticket and alerting our senior technicians. How long has the server been down? [CREATE_TICKET: severity=critical, product=Hardware]

Customer: "What time do you close today?"
You: We're open until 6 PM today, and we have 24/7 emergency support for urgent technical issues. Is there anything else I can help you with?

=== BE GENUINELY INTELLIGENT ===
- Adapt your approach based on how the customer communicates
- Ask follow-up questions that actually help understand the problem
- Don't follow scripts - think about what would be most helpful
- If you're unsure about severity or category, use your best judgment
- Focus on solving the customer's actual problem

Remember: You're not following rules, you're being intelligent and helpful.

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
    
