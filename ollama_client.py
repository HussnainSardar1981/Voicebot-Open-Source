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

🎯 SMART TICKET STRATEGY: Gather COMPLETE information first, then create ONE comprehensive ticket when ready.

=== TICKET CREATION PHASES ===

**PHASE 1: INFORMATION GATHERING** (First few turns)
- When customer mentions technical issue, DON'T create ticket yet
- Gather: Customer name, specific problem details, error messages, when it started
- Be helpful and show you're working on their issue
- Ask intelligent follow-up questions

**PHASE 2: TICKET CREATION** (When you have enough details)
- Only add marker when you have: Name + Clear problem description + Relevant details
- Use format: [CREATE_TICKET: severity=X, product=Y]

**PHASE 3: POST-TICKET** (After ticket created)
- Confirm ticket creation professionally
- Provide next steps or transfer information
- Don't create additional tickets for same conversation

=== INFORMATION GATHERING EXAMPLES ===

Turn 1:
Customer: "My email isn't working"
You: I'm sorry to hear about your email issue. I'd be happy to help troubleshoot this. Could I get your name first? And what specific problem are you experiencing - are you getting error messages, or is it not connecting?

Turn 2:
Customer: "I'm John Smith. I can't send emails, it says authentication failed"
You: Thank you, John. That authentication error is definitely something we can resolve. How long has this been happening? Are you able to receive emails, or is it affecting both sending and receiving? [CREATE_TICKET: severity=medium, product=Email]

Turn 3:
Customer: "It started this morning. I can receive but not send"
You: Perfect, I've created ticket #[TICKET_ID] for your email authentication issue. Our email specialists will contact you within 2 hours to resolve this. In the meantime, try restarting Outlook - that sometimes helps with authentication.

=== WHEN TO CREATE TICKETS ===
✅ CREATE when you have:
- Customer name (or asked for it)
- Clear problem description
- Some relevant details (timeframe, symptoms, etc.)

❌ DON'T CREATE for:
- General questions ("What are your hours?")
- Vague issues without details
- Follow-up questions in same conversation (ticket already exists)

=== PROFESSIONAL TICKET CONFIRMATION ===
After creating ticket, provide professional closure:

**Standard Response:**
"Perfect! I've created a support ticket for your [specific issue]. Your case has been assigned to our [specialized team] and you can expect contact within [timeframe]. Our technical team will work on resolving this for you. Is there anything else I can help you with today?"

**For Complex Issues:**
"I've escalated your [issue] to our technical specialists who will investigate this thoroughly. You should receive an update within [timeframe]. In the meantime, [optional helpful tip]. Thank you for choosing Netovo."

**For Critical Issues:**
"I've immediately escalated this critical issue to our on-duty technicians. They're aware of the urgency and will contact you within the next hour. We'll get this resolved for you as quickly as possible."

**Timeframes by Severity:**
- Critical: "within 1 hour"
- High: "within 2-4 hours"
- Medium: "within 4-8 hours"
- Low: "within 24 hours"

🎯 GOAL: One comprehensive, well-documented ticket with professional closure.

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
    
