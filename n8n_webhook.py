#!/usr/bin/env python3
"""
n8n Webhook Integration
Sends voicebot data to existing n8n workflow for Atera ticket creation
"""

import requests
import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/create-ticket"


def create_ticket_via_n8n_blocking(
    caller_id: str,
    transcript: str,
    severity: str,
    customer_name: str = ""
) -> Optional[str]:
    """
    Send ticket data to n8n webhook (synchronous, blocking)
    This is the internal implementation that does the actual work.
    """
    try:
        # AI-determined product family from conversation analysis
        try:
            # Extract conversation messages for intelligent analysis
            messages = []
            if transcript:
                lines = transcript.split('\n')
                for line in lines:
                    if line.startswith('Customer: '):
                        messages.append({'role': 'user', 'content': line[10:]})
                    elif line.startswith('VoiceBot: '):
                        messages.append({'role': 'assistant', 'content': line[10:]})
            product_family = detect_product_family(messages)
        except:
            product_family = "General Support"

        payload = {
            'caller_id': caller_id,
            'transcript': transcript,
            'customer_name': customer_name,
            'severity': severity,
            'product_family': product_family,
            'timestamp': datetime.now().isoformat(),
            'source': 'voicebot',
            # Additional NETOVO required fields
            'internal_notes': f"VoiceBot Auto-Generated Ticket\nCaller: {caller_id}\nCustomer: {customer_name}\nProduct: {product_family}\nSeverity: {severity}\n\nFull Transcript:\n{transcript}",
            'contract': 'AUTO_DETECT',  # Will be handled by n8n workflow
            'field_technician': 'UNASSIGNED'  # As per NETOVO requirements
        }

        logger.info(f"Creating ticket via n8n: severity={severity}, product={product_family}, caller={caller_id}")

        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            ticket_id = result.get('ticket_id') or result.get('ticket_number')
            logger.info(f"✅ Ticket created successfully: {ticket_id}")
            return ticket_id
        else:
            logger.error(f"❌ n8n webhook failed: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("❌ n8n webhook timeout (>10 seconds)")
        return None
    except Exception as e:
        logger.error(f"❌ n8n webhook error: {e}")
        return None


def create_ticket_via_n8n(
    caller_id: str,
    transcript: str,
    severity: str,
    customer_name: str = ""
) -> None:
    """
    Send ticket data to n8n webhook (NON-BLOCKING via background thread)

    This function immediately returns and creates the ticket in the background.
    The conversation can continue without waiting for the webhook response.

    Args:
        caller_id: Phone number
        transcript: Full conversation transcript
        severity: critical/high/medium/low
        customer_name: Extracted customer name (if any)

    Returns:
        None (runs in background)
    """
    def _background_ticket_creation():
        """Background thread function for ticket creation"""
        try:
            logger.info(f"🎫 Background ticket creation started for caller: {caller_id}")
            ticket_id = create_ticket_via_n8n_blocking(
                caller_id=caller_id,
                transcript=transcript,
                severity=severity,
                customer_name=customer_name
            )

            if ticket_id:
                logger.info(f"✅ Background ticket creation successful: {ticket_id}")
            else:
                logger.warning(f"⚠️ Background ticket creation failed for caller: {caller_id}")

        except Exception as e:
            logger.error(f"❌ Background ticket creation error: {e}")

    # Start ticket creation in background thread (non-blocking)
    thread = threading.Thread(
        target=_background_ticket_creation,
        name=f"TicketCreation-{caller_id}",
        daemon=True  # Dies with main process
    )
    thread.start()
    logger.info(f"🚀 Ticket creation started in background for {caller_id}")

    # Return immediately - conversation can continue


def format_transcript(messages: list) -> str:
    """Format conversation messages into readable transcript"""
    transcript = ""
    for msg in messages:
        role = "Customer" if msg.get('role') == 'user' else "VoiceBot"
        content = msg.get('content', '')
        transcript += f"{role}: {content}\n\n"
    return transcript.strip()


def detect_product_family(messages: list) -> str:
    """
    Detect product family from conversation
    Based on common NETOVO service categories
    """
    full_text = " ".join([msg.get('content', '') for msg in messages]).lower()

    # Email-related issues
    if any(word in full_text for word in ['email', 'outlook', 'mail', 'exchange', 'smtp', 'imap']):
        return "Email Services"

    # Printer/printing issues
    if any(word in full_text for word in ['printer', 'print', 'printing', 'paper', 'toner', 'cartridge']):
        return "Printing Services"

    # Network/connectivity issues
    if any(word in full_text for word in ['network', 'internet', 'wifi', 'connection', 'router', 'switch']):
        return "Network Services"

    # Software issues
    if any(word in full_text for word in ['software', 'application', 'program', 'app', 'system', 'windows', 'microsoft']):
        return "Software Support"

    # Hardware issues
    if any(word in full_text for word in ['computer', 'laptop', 'desktop', 'hardware', 'device', 'machine']):
        return "Hardware Support"

    # Security issues
    if any(word in full_text for word in ['password', 'login', 'access', 'security', 'account', 'virus']):
        return "Security Services"

    # Default fallback
    return "General Support"


def extract_customer_name(messages: list) -> str:
    """
    Extract customer name from conversation
    Looks for patterns: "I'm John", "This is Mary", etc.
    """
    for msg in messages:
        if msg.get('role') == 'user':
            content = msg.get('content', '').lower()

            # Common introduction patterns
            if "i'm " in content or "i am " in content:
                words = content.replace("i'm", "").replace("i am", "").split()
                if words and len(words[0]) > 2:
                    return words[0].strip('.,!?').title()

            if "this is " in content:
                words = content.split("this is ")[1].split()
                if words and len(words[0]) > 2:
                    return words[0].strip('.,!?').title()

            if "my name is " in content:
                words = content.split("my name is ")[1].split()
                if words and len(words[0]) > 2:
                    return words[0].strip('.,!?').title()

    return "Unknown Customer"
