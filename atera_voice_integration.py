#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA Voice Integration for NETOVO VoiceBot Conversation Flow

Purpose: Provides natural voice responses for ATERA MSP operations including
         ticket management, customer service, and support workflows.

This module handles:
- Voice query recognition for support requests
- Natural language responses for ticket information
- Customer identification and verification
- Ticket creation and management workflows
- Integration with existing conversation system

Key Features:
- Natural language processing for support queries
- Voice-optimized response generation
- Context preservation during ticket workflows
- Smart escalation handling for complex issues
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Import ATERA components
try:
    from atera_client import ATERAClient
    from atera_config import (
        VOICE_TEMPLATES, PRIORITY_VOICE_MAPPING, STATUS_VOICE_MAPPING,
        TICKET_MANAGEMENT_CONFIG, CUSTOMER_SERVICE_CONFIG
    )
except ImportError:
    # Fallback for development
    ATERAClient = None
    VOICE_TEMPLATES = {}
    PRIORITY_VOICE_MAPPING = {}
    STATUS_VOICE_MAPPING = {}
    TICKET_MANAGEMENT_CONFIG = {}
    CUSTOMER_SERVICE_CONFIG = {}

logger = logging.getLogger(__name__)

class ATERAVoiceHandler:
    """
    Voice handler for ATERA MSP operations in VoiceBot conversations.

    This class integrates with the existing conversation flow to provide
    natural voice responses for support ticket management and customer service.
    """

    def __init__(self, client: ATERAClient = None):
        """Initialize voice handler with ATERA client."""
        self.atera_client = client or (ATERAClient() if ATERAClient else None)
        self.conversation_context = {}
        self.current_customer = None
        self.pending_ticket_creation = {}

        # Support query patterns
        self.query_patterns = {
            "ticket_status": [
                r".*ticket.*status.*",
                r".*check.*ticket.*",
                r".*ticket.*\d+.*",
                r".*status.*ticket.*",
                r".*my.*tickets.*",
                r".*open.*tickets.*"
            ],
            "create_ticket": [
                r".*create.*ticket.*",
                r".*new.*ticket.*",
                r".*need.*help.*",
                r".*support.*request.*",
                r".*technical.*issue.*",
                r".*problem.*with.*",
                r".*not.*working.*",
                r".*broken.*",
                r".*issue.*with.*"
            ],
            "customer_lookup": [
                r".*who.*am.*i.*",
                r".*my.*account.*",
                r".*customer.*information.*",
                r".*account.*details.*"
            ],
            "general_support": [
                r".*help.*",
                r".*support.*",
                r".*assistance.*",
                r".*technical.*support.*"
            ]
        }

        # Response personalization
        self.response_variations = {
            "greeting": [
                "Let me look up your account information.",
                "I'll check your support tickets and account status.",
                "Accessing your customer information now."
            ],
            "checking": [
                "One moment while I check your tickets.",
                "Let me look up your support history.",
                "Checking your account status now."
            ],
            "no_connection": [
                "I'm unable to access the support system right now.",
                "The ticketing system appears to be unavailable.",
                "I cannot retrieve your ticket information at this moment."
            ]
        }

        logger.info("ATERAVoiceHandler initialized")

    def is_support_query(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if user input is a support-related query.

        Args:
            user_input: User's spoken input

        Returns:
            Tuple of (is_support_query, query_type)
        """
        if not user_input:
            return False, None

        user_input_lower = user_input.lower()

        # Check for support keywords
        support_keywords = [
            "ticket", "support", "help", "issue", "problem", "broken",
            "not working", "error", "technical", "assistance", "trouble"
        ]

        has_support_keyword = any(keyword in user_input_lower for keyword in support_keywords)

        if not has_support_keyword:
            return False, None

        # Determine specific query type
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.match(pattern, user_input_lower):
                    logger.debug(f"Detected support query type: {query_type}")
                    return True, query_type

        # Generic support query
        return True, "general_support"

    def handle_support_query(self, user_input: str, caller_phone: str = None,
                           conversation_context: Dict = None) -> Dict:
        """
        Handle support-related query and generate voice response.

        Args:
            user_input: User's spoken input
            caller_phone: Phone number of caller (for customer lookup)
            conversation_context: Current conversation context

        Returns:
            Dictionary with voice response and metadata
        """
        try:
            # Check if this is a support query
            is_support, query_type = self.is_support_query(user_input)

            if not is_support:
                return {
                    "is_support_query": False,
                    "voice_response": None,
                    "voice_type": "default"
                }

            # Update conversation context
            self.conversation_context = conversation_context or {}

            # Check ATERA service availability
            if not self.atera_client:
                return self._generate_error_response("service_unavailable")

            # Try to identify customer first
            if not self.current_customer and caller_phone:
                self.current_customer = self.atera_client.search_customer_by_phone(caller_phone)

            # Generate response based on query type
            if query_type == "ticket_status":
                return self._handle_ticket_status_query(user_input)
            elif query_type == "create_ticket":
                return self._handle_ticket_creation_query(user_input)
            elif query_type == "customer_lookup":
                return self._handle_customer_lookup_query(user_input)
            else:
                return self._handle_general_support_query(user_input)

        except Exception as e:
            logger.error(f"Error handling support query: {e}")
            return self._generate_error_response("processing_error", str(e))

    def _handle_ticket_status_query(self, user_input: str) -> Dict:
        """Handle ticket status queries."""
        try:
            if not self.current_customer:
                return {
                    "is_support_query": True,
                    "voice_response": "I need to identify your account first. Could you please provide your company name or phone number?",
                    "voice_type": "helping",
                    "requires_customer_info": True
                }

            # Get customer's tickets
            summary = self.atera_client.get_customer_ticket_summary(self.current_customer['id'])

            # Check for specific ticket number in query
            ticket_number_match = re.search(r'\b(\d{4,})\b', user_input)
            if ticket_number_match:
                ticket_id = ticket_number_match.group(1)
                return self._handle_specific_ticket_query(ticket_id)

            # General ticket status
            voice_response = summary['voice_summary']

            # Add helpful follow-up
            if summary.get('open_tickets', 0) > 0:
                voice_response += " Would you like details about any specific ticket?"

            return {
                "is_support_query": True,
                "voice_response": voice_response,
                "voice_type": "technical",
                "customer_name": self.current_customer['voice_name'],
                "ticket_count": summary.get('total_tickets', 0),
                "requires_escalation": False
            }

        except Exception as e:
            logger.error(f"Error handling ticket status query: {e}")
            return self._generate_error_response("query_error", str(e))

    def _handle_specific_ticket_query(self, ticket_id: str) -> Dict:
        """Handle queries about specific ticket numbers."""
        try:
            # Get customer's tickets and find the specific one
            tickets = self.atera_client.get_tickets(
                customer_id=self.current_customer['id'],
                limit=50
            )

            target_ticket = next((t for t in tickets if str(t['id']) == ticket_id), None)

            if not target_ticket:
                voice_response = f"I couldn't find ticket {ticket_id} in your account. Could you double-check the ticket number?"
            else:
                # Generate detailed ticket response
                status_info = STATUS_VOICE_MAPPING.get(target_ticket['status'], {})
                status_description = status_info.get('voice_description', target_ticket['status'])

                voice_response = f"Ticket {ticket_id} for {target_ticket['voice_title']} is {status_description}."

                if target_ticket['technician'] != "Unassigned":
                    voice_response += f" Your technician is {target_ticket['technician']}."

                next_step = status_info.get('next_step')
                if next_step:
                    voice_response += f" {next_step}."

            return {
                "is_support_query": True,
                "voice_response": voice_response,
                "voice_type": "technical",
                "ticket_found": target_ticket is not None,
                "requires_escalation": False
            }

        except Exception as e:
            logger.error(f"Error handling specific ticket query: {e}")
            return self._generate_error_response("query_error", str(e))

    def _handle_ticket_creation_query(self, user_input: str) -> Dict:
        """Handle ticket creation requests."""
        try:
            if not self.current_customer:
                return {
                    "is_support_query": True,
                    "voice_response": "I'd be happy to create a support ticket for you. First, could you provide your company name so I can locate your account?",
                    "voice_type": "helping",
                    "requires_customer_info": True,
                    "next_action": "create_ticket"
                }

            # Extract issue description from input
            issue_description = self._extract_issue_description(user_input)

            if not issue_description:
                return {
                    "is_support_query": True,
                    "voice_response": "I'll create a support ticket for you. Could you please describe the issue you're experiencing?",
                    "voice_type": "helping",
                    "awaiting_description": True,
                    "next_action": "get_issue_description"
                }

            # Determine priority based on urgency keywords
            priority = self._determine_priority_from_input(user_input)

            # Create the ticket
            result = self.atera_client.create_ticket(
                customer_id=self.current_customer['id'],
                title=issue_description[:100],  # Limit title length
                description=issue_description,
                priority=priority
            )

            if result['success']:
                voice_response = result['voice_response']
                voice_response += f" I've also notified our technical team. Is there anything else I can help you with?"
            else:
                voice_response = result['voice_response']

            return {
                "is_support_query": True,
                "voice_response": voice_response,
                "voice_type": "helping",
                "ticket_created": result['success'],
                "ticket_id": result.get('ticket_id'),
                "requires_escalation": not result['success']
            }

        except Exception as e:
            logger.error(f"Error handling ticket creation: {e}")
            return self._generate_error_response("query_error", str(e))

    def _handle_customer_lookup_query(self, user_input: str) -> Dict:
        """Handle customer information lookup queries."""
        try:
            if not self.current_customer:
                return {
                    "is_support_query": True,
                    "voice_response": "I don't have your account information yet. Could you provide your company name or phone number?",
                    "voice_type": "helping",
                    "requires_customer_info": True
                }

            # Provide customer information summary
            customer = self.current_customer
            voice_response = f"You're calling from {customer['voice_name']}."

            if customer.get('contact_person'):
                voice_response += f" Your primary contact is {customer['contact_person']}."

            # Add ticket summary
            summary = self.atera_client.get_customer_ticket_summary(customer['id'])
            if summary.get('open_tickets', 0) > 0:
                voice_response += f" You currently have {summary['open_tickets']} open support tickets."
            else:
                voice_response += " You have no open support tickets."

            return {
                "is_support_query": True,
                "voice_response": voice_response,
                "voice_type": "default",
                "customer_identified": True,
                "requires_escalation": False
            }

        except Exception as e:
            logger.error(f"Error handling customer lookup: {e}")
            return self._generate_error_response("query_error", str(e))

    def _handle_general_support_query(self, user_input: str) -> Dict:
        """Handle general support queries."""
        try:
            if not self.current_customer:
                voice_response = "I'd be happy to help you with technical support. Could you provide your company name so I can access your account?"
                requires_customer_info = True
            else:
                # Provide general support options
                customer_name = self.current_customer['voice_name']
                voice_response = f"I can help you with technical support for {customer_name}. "
                voice_response += "I can check your current tickets, create a new support request, or transfer you to a technician. What would you like to do?"
                requires_customer_info = False

            return {
                "is_support_query": True,
                "voice_response": voice_response,
                "voice_type": "helping",
                "requires_customer_info": requires_customer_info,
                "next_action": "support_menu"
            }

        except Exception as e:
            logger.error(f"Error handling general support query: {e}")
            return self._generate_error_response("query_error", str(e))

    def identify_customer_by_name(self, company_name: str) -> Dict:
        """
        Identify customer by company name.

        Args:
            company_name: Company name provided by caller

        Returns:
            Customer identification result
        """
        try:
            customers = self.atera_client.get_customers(search_term=company_name, limit=10)

            if not customers:
                return {
                    "success": False,
                    "voice_response": f"I couldn't find a customer account for {company_name}. Could you spell that differently or provide your phone number?"
                }

            if len(customers) == 1:
                self.current_customer = customers[0]
                return {
                    "success": True,
                    "customer": customers[0],
                    "voice_response": f"Thank you, I found your account for {customers[0]['voice_name']}. How can I help you today?"
                }

            # Multiple matches - need clarification
            if len(customers) <= 3:
                names = [c['voice_name'] for c in customers]
                name_list = ", ".join(names[:-1]) + f", or {names[-1]}" if len(names) > 1 else names[0]
                voice_response = f"I found multiple matches: {name_list}. Which one is correct?"
            else:
                voice_response = f"I found {len(customers)} companies with similar names. Could you be more specific?"

            return {
                "success": False,
                "multiple_matches": customers,
                "voice_response": voice_response
            }

        except Exception as e:
            logger.error(f"Error identifying customer: {e}")
            return {
                "success": False,
                "voice_response": "I'm having trouble accessing customer information. Please try again."
            }

    def _extract_issue_description(self, user_input: str) -> str:
        """Extract issue description from user input."""
        # Remove common prefixes
        prefixes_to_remove = [
            "i need help with",
            "i have a problem with",
            "there's an issue with",
            "i'm having trouble with",
            "create a ticket for",
            "i need support for"
        ]

        description = user_input.lower()
        for prefix in prefixes_to_remove:
            if description.startswith(prefix):
                description = description[len(prefix):].strip()
                break

        # Clean up and capitalize
        description = description.strip()
        if description:
            description = description[0].upper() + description[1:]

        return description if len(description) > 5 else ""

    def _determine_priority_from_input(self, user_input: str) -> str:
        """Determine ticket priority from user input keywords."""
        user_input_lower = user_input.lower()

        critical_keywords = ["emergency", "urgent", "critical", "down", "outage", "broken", "can't work"]
        high_keywords = ["important", "asap", "soon", "affecting", "impact"]
        low_keywords = ["when convenient", "low priority", "minor", "small issue"]

        if any(keyword in user_input_lower for keyword in critical_keywords):
            return "Critical"
        elif any(keyword in user_input_lower for keyword in high_keywords):
            return "High"
        elif any(keyword in user_input_lower for keyword in low_keywords):
            return "Low"
        else:
            return "Medium"  # Default priority

    def _generate_error_response(self, error_type: str, error_details: str = None) -> Dict:
        """Generate error response for voice output."""
        error_responses = {
            "service_unavailable": "I'm unable to access the support system right now. Let me transfer you to our technical support team.",
            "processing_error": "I encountered an issue while processing your request. Let me connect you with a support technician.",
            "query_error": "I couldn't process your support request. Please try rephrasing or let me transfer you to technical support.",
            "customer_not_found": "I couldn't locate your account in our system. Let me transfer you to customer service for assistance."
        }

        voice_response = error_responses.get(error_type, "I'm experiencing technical difficulties. Let me transfer you to support.")

        return {
            "is_support_query": True,
            "voice_response": voice_response,
            "voice_type": "empathetic",
            "error": True,
            "error_type": error_type,
            "requires_escalation": True
        }

    def reset_context(self):
        """Reset conversation context for new caller."""
        self.current_customer = None
        self.conversation_context = {}
        self.pending_ticket_creation = {}

# =============================================================================
# INTEGRATION WITH VOICEBOT_MAIN.PY
# =============================================================================

def integrate_with_voicebot():
    """
    Integration instructions for voicebot_main.py

    Add this code to your existing voicebot_main.py:

    1. Import at the top:
       from atera_voice_integration import ATERAVoiceHandler

    2. In main() function, after initializing clients:
       atera_voice = ATERAVoiceHandler()

    3. In conversation_loop(), before processing with AI:
       # Check if this is a support query
       support_response = atera_voice.handle_support_query(
           user_input,
           caller_phone=caller_phone,  # Extract from AGI
           conversation_context={
               "conversation_turn": turn,
               "user_context": user_context
           }
       )

       if support_response["is_support_query"]:
           # Handle support query
           voice_type = support_response.get("voice_type", "helping")
           response_text = support_response["voice_response"]

           # Check if escalation needed
           if support_response.get("requires_escalation", False):
               response_text += " I'm transferring you to technical support now."
               # Add escalation logic here

           # Check if customer info needed
           if support_response.get("requires_customer_info", False):
               # Set flag to collect customer info in next turn
               user_context["awaiting_customer_info"] = True

           # Convert to audio and play
           tts_file = tts_client.synthesize(response_text, voice_type)
           if tts_file:
               audio_file = convert_audio_for_asterisk(tts_file)
               if audio_file:
                   agi.stream_file(audio_file)

           continue  # Skip AI processing for support queries

    4. Add cleanup:
       if 'atera_voice' in locals():
           atera_voice.reset_context()
    """
    pass

# Example usage patterns
EXAMPLE_SUPPORT_QUERIES = {
    "ticket_status": [
        "What's the status of my tickets?",
        "Check my open tickets",
        "Is ticket 12345 resolved?",
        "Any updates on my support request?"
    ],
    "create_ticket": [
        "I need to create a support ticket",
        "My email is not working",
        "The server is down",
        "I need technical help"
    ],
    "customer_lookup": [
        "Who am I in your system?",
        "What's my account information?",
        "What company am I calling from?"
    ],
    "general_support": [
        "I need technical support",
        "Can you help me?",
        "I'm having computer problems",
        "Transfer me to IT support"
    ]
}

if __name__ == "__main__":
    # Test the voice integration
    print("Testing ATERA Voice Integration...")

    handler = ATERAVoiceHandler()

    # Test query recognition
    test_queries = [
        "I need to check my ticket status",
        "Create a new support ticket",
        "My server is down",
        "What's the weather today"  # Non-support query
    ]

    for query in test_queries:
        is_support, query_type = handler.is_support_query(query)
        print(f"Query: '{query}' -> Support: {is_support}, Type: {query_type}")

    # Test response generation (if service is available)
    if handler.atera_client:
        test_response = handler.handle_support_query("I need to check my tickets")
        print(f"\nSample response: {test_response}")

    print("ATERA voice integration test completed.")