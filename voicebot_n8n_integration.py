#!/usr/bin/env python3
"""
VoiceBot N8N Integration Code
Add this to your voicebot_main.py to enable Atera ticket creation via n8n

This code shows how to integrate without modifying your working voicebot core logic
"""

# ADD TO IMPORTS SECTION of voicebot_main.py:
from integrations.n8n_client import N8NClient, N8NError

# ADD AFTER OTHER GLOBAL VARIABLES:
# Global N8N client for ticket creation
_n8n_client = None

def get_n8n_client():
    """Get or create N8N client instance"""
    global _n8n_client
    if _n8n_client is None:
        _n8n_client = N8NClient()
    return _n8n_client

def create_ticket_from_call(caller_id, transcript, customer_name=None):
    """
    Create Atera ticket via n8n workflow

    Args:
        caller_id: Phone number from AGI
        transcript: User's spoken input
        customer_name: Optional customer name (extracted or provided)

    Returns:
        dict: Ticket creation result or None if failed
    """
    try:
        n8n = get_n8n_client()

        # Prepare ticket data
        ticket_data = {
            "caller_id": caller_id,
            "transcript": transcript,
            "customer_name": customer_name or "Unknown Customer"
        }

        # Create ticket via n8n
        result = n8n.create_ticket(ticket_data)

        logger.info(f"Ticket created successfully: {result.get('ticket_number')}")
        return result

    except N8NError as e:
        logger.error(f"Ticket creation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}")
        return None

def extract_customer_name(transcript):
    """
    Simple customer name extraction from transcript
    You can enhance this with better NLP if needed
    """
    transcript_lower = transcript.lower()

    # Look for common patterns
    name_patterns = [
        "my name is ",
        "this is ",
        "i'm ",
        "i am ",
        "speaking with "
    ]

    for pattern in name_patterns:
        if pattern in transcript_lower:
            # Extract name after pattern
            start_idx = transcript_lower.find(pattern) + len(pattern)
            remaining = transcript[start_idx:].strip()
            # Take first few words as name
            name_parts = remaining.split()[:3]  # Max 3 words for name
            if name_parts:
                return " ".join(name_parts).title()

    return None

# MODIFY YOUR CONVERSATION LOOP IN voicebot_main.py:
# Add this code in the conversation_loop function after getting user transcript

"""
# EXAMPLE INTEGRATION IN conversation_loop():

def conversation_loop(agi, tts, asr, ollama, recorder):
    # ... existing code ...

    for turn in range(max_turns):
        logger.info(f"Conversation turn {turn + 1}")

        # Get user input (existing code)
        transcript = recorder.get_user_input_with_mixmonitor(
            timeout=CONVERSATION_CONFIG["input_timeout"]
        )

        if not agi.connected:
            logger.info("Call disconnected")
            break

        if transcript:
            logger.info(f"User said: {transcript}")

            # TICKET CREATION - ADD THIS SECTION:
            # Create ticket on first meaningful input
            if turn == 0 or any(word in transcript.lower() for word in ['problem', 'issue', 'help', 'support']):
                caller_id = agi.env.get('agi_callerid', 'Unknown')
                customer_name = extract_customer_name(transcript)

                ticket_result = create_ticket_from_call(caller_id, transcript, customer_name)

                if ticket_result:
                    # Include ticket number in response
                    ticket_number = ticket_result.get('ticket_number')
                    logger.info(f"Ticket {ticket_number} created for call")

                    # Generate AI response
                    response = ollama.generate(transcript)

                    # Add ticket info to response
                    response += f" I've created ticket number {ticket_number} for your request."
                else:
                    # Continue without ticket
                    logger.warning("Failed to create ticket, continuing conversation")
                    response = ollama.generate(transcript)
            else:
                # Normal conversation without ticket creation
                response = ollama.generate(transcript)
            # END TICKET CREATION SECTION

            # ... rest of existing conversation logic ...
"""

# SIMPLE TEST FUNCTION - ADD TO END OF voicebot_main.py:
def test_n8n_integration():
    """Test n8n integration without full voicebot"""
    logger.info("Testing N8N integration...")

    # Test health check
    n8n = get_n8n_client()
    if not n8n.health_check():
        logger.error("N8N health check failed")
        return False

    # Test ticket creation
    test_result = create_ticket_from_call(
        caller_id="+15551234567",
        transcript="Test call - my computer is not working properly",
        customer_name="Test User"
    )

    if test_result:
        logger.info(f"Test successful: {test_result}")
        return True
    else:
        logger.error("Test ticket creation failed")
        return False

# USAGE NOTES:
"""
1. Copy n8n_client.py to your integrations/ directory
2. Add the imports and functions above to voicebot_main.py
3. Modify your conversation_loop as shown in the example
4. Test with: test_n8n_integration() function
5. The ticket creation happens automatically on meaningful user input
6. Your existing voicebot logic remains unchanged
7. If n8n fails, conversation continues normally
"""
