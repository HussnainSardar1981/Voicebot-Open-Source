#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA Configuration Module for NETOVO VoiceBot Integration

Purpose: Centralized configuration management for ATERA MSP platform integration
         with environment-specific settings and voice optimization parameters.

Configuration includes:
- ATERA API connection settings
- Voice integration parameters for ticket management
- Customer service workflow configurations
- Performance and security settings
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# ATERA CONNECTION CONFIGURATION
# =============================================================================

# Base ATERA Configuration
ATERA_CONFIG = {
    # Connection settings
    "api_key": os.getenv("ATERA_API_KEY", "your_atera_api_key_here"),
    "base_url": "https://app.atera.com/api/v3",

    # API behavior settings
    "timeout": 15.0,
    "max_retries": 3,
    "rate_limit_delay": 1.0,
    "max_items_per_request": 50,

    # Environment settings
    "environment": os.getenv("ENVIRONMENT", "development"),  # development, staging, production
    "debug_mode": os.getenv("ATERA_DEBUG", "false").lower() == "true"
}

# =============================================================================
# VOICE INTEGRATION CONFIGURATION
# =============================================================================

# Ticket Management Settings
TICKET_MANAGEMENT_CONFIG = {
    # Voice interaction settings
    "max_voice_tickets": 5,  # Maximum tickets to mention in voice response
    "include_closed_tickets": False,  # Include closed tickets in summaries
    "voice_priority_threshold": "Medium",  # Minimum priority to announce

    # Ticket creation settings
    "default_priority": "Medium",
    "default_urgency": "Medium",
    "auto_assign_technician": False,
    "voicebot_source_tag": "VoiceBot API",

    # Voice response settings
    "use_customer_names": True,
    "include_time_information": True,
    "include_technician_info": True,
    "use_technical_voice": True  # Use technical voice type for ticket info
}

# Customer Service Settings
CUSTOMER_SERVICE_CONFIG = {
    # Customer lookup settings
    "enable_phone_lookup": True,
    "fuzzy_name_matching": True,
    "include_inactive_customers": False,

    # Voice interaction settings
    "customer_greeting_template": "Hello {customer_name}, how can I help you today?",
    "ticket_creation_confirmation": True,
    "read_back_ticket_details": True,

    # Privacy settings
    "mask_sensitive_info": True,
    "allow_ticket_details_over_phone": True,
    "require_verification": False  # Set to True for enhanced security
}

# =============================================================================
# VOICE RESPONSE TEMPLATES
# =============================================================================

# Templates for different types of voice responses
VOICE_TEMPLATES = {
    "customer_greeting": [
        "Hello {customer_name}, I see you're calling about your account.",
        "Hi {customer_name}, how can I assist you with your IT support today?",
        "Good {time_of_day} {customer_name}, what can I help you with?"
    ],

    "ticket_status": {
        "open": "Your ticket {ticket_id} for {issue} is currently open and assigned to {technician}.",
        "pending": "Ticket {ticket_id} is pending additional information. {technician} will contact you soon.",
        "resolved": "Your ticket {ticket_id} has been resolved. The issue was: {resolution}.",
        "closed": "Ticket {ticket_id} is now closed. The final resolution was: {resolution}."
    },

    "ticket_creation": {
        "success": "I've created ticket number {ticket_id} for your {issue}. It's been assigned {priority} priority and will be handled by our technical team.",
        "failed": "I'm unable to create a ticket right now. Please try again or call our support line directly.",
        "confirmation": "Let me confirm your ticket details: Issue: {issue}, Priority: {priority}, Customer: {customer_name}. Is this correct?"
    },

    "no_tickets": [
        "You currently have no open support tickets. All your previous issues have been resolved.",
        "Great news! You don't have any active tickets. Your systems are running smoothly.",
        "No open tickets found for your account. Everything appears to be working well."
    ],

    "multiple_tickets": "You have {count} open tickets. The most recent is {latest_ticket} created {time_ago}.",

    "alerts_summary": {
        "none": "No active alerts for your systems. Everything is running normally.",
        "few": "There are {count} minor alerts that don't require immediate attention.",
        "many": "There are {count} alerts including {critical_count} that need immediate attention."
    },

    "system_unavailable": [
        "I'm unable to access your ticket information right now. Please try again in a moment.",
        "The support system is temporarily unavailable. Please call our direct support line.",
        "I cannot retrieve your account information at this time. Please contact support directly."
    ]
}

# =============================================================================
# TICKET PRIORITY AND STATUS MAPPING
# =============================================================================

# Priority levels mapping for voice responses
PRIORITY_VOICE_MAPPING = {
    "Low": {
        "voice_description": "low priority",
        "urgency_level": 1,
        "expected_response": "within 2 business days",
        "escalation_threshold": False
    },
    "Medium": {
        "voice_description": "standard priority",
        "urgency_level": 2,
        "expected_response": "within 1 business day",
        "escalation_threshold": False
    },
    "High": {
        "voice_description": "high priority",
        "urgency_level": 3,
        "expected_response": "within 4 hours",
        "escalation_threshold": True
    },
    "Critical": {
        "voice_description": "critical priority",
        "urgency_level": 4,
        "expected_response": "immediately",
        "escalation_threshold": True
    }
}

# Status mapping for voice responses
STATUS_VOICE_MAPPING = {
    "Open": {
        "voice_description": "open and being worked on",
        "customer_action": "none required",
        "next_step": "technician will contact you"
    },
    "Pending": {
        "voice_description": "waiting for additional information",
        "customer_action": "please provide requested details",
        "next_step": "ticket will resume once info is received"
    },
    "Resolved": {
        "voice_description": "resolved",
        "customer_action": "please test the fix",
        "next_step": "ticket will close automatically if no issues"
    },
    "Closed": {
        "voice_description": "closed and completed",
        "customer_action": "none required",
        "next_step": "contact us if issue returns"
    }
}

# =============================================================================
# INTEGRATION SETTINGS
# =============================================================================

# Socket communication settings (following existing pattern)
ATERA_SOCKET_CONFIG = {
    "socket_path": "/tmp/netovo_atera.sock",
    "buffer_size": 4096,
    "connection_timeout": 5.0,
    "request_timeout": 15.0
}

# Performance settings
PERFORMANCE_CONFIG = {
    "cache_customer_lookups": True,
    "cache_timeout_minutes": 15,
    "max_concurrent_requests": 5,
    "request_queue_size": 100,
    "enable_background_sync": True
}

# =============================================================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# =============================================================================

def get_environment_config(environment: str = None) -> Dict:
    """
    Get environment-specific configuration overrides.

    Args:
        environment: Target environment (development, staging, production)

    Returns:
        Dictionary with environment-specific settings
    """
    env = environment or ATERA_CONFIG["environment"]

    if env == "development":
        return {
            "debug_mode": True,
            "rate_limit_delay": 0.1,  # Faster for development
            "max_retries": 1,
            "include_closed_tickets": True,  # Show all tickets in dev
            "require_verification": False
        }
    elif env == "staging":
        return {
            "debug_mode": True,
            "rate_limit_delay": 0.5,
            "max_retries": 2,
            "include_closed_tickets": False,
            "require_verification": False
        }
    elif env == "production":
        return {
            "debug_mode": False,
            "rate_limit_delay": 1.0,
            "max_retries": 3,
            "include_closed_tickets": False,
            "require_verification": True  # Enhanced security in production
        }
    else:
        return {}

def apply_environment_config():
    """Apply environment-specific configuration overrides."""
    env_config = get_environment_config()

    # Update global configurations
    ATERA_CONFIG.update(env_config)

    # Update other config sections
    for key in ["include_closed_tickets", "require_verification"]:
        if key in env_config:
            if key in TICKET_MANAGEMENT_CONFIG:
                TICKET_MANAGEMENT_CONFIG[key] = env_config[key]
            elif key in CUSTOMER_SERVICE_CONFIG:
                CUSTOMER_SERVICE_CONFIG[key] = env_config[key]

# Apply environment configuration on import
apply_environment_config()

# =============================================================================
# VALIDATION AND TESTING
# =============================================================================

def validate_config() -> List[str]:
    """
    Validate configuration settings and return list of issues.

    Returns:
        List of configuration validation errors
    """
    issues = []

    # Required settings
    if not ATERA_CONFIG["api_key"] or ATERA_CONFIG["api_key"] == "your_atera_api_key_here":
        issues.append("ATERA API key not configured")

    if not ATERA_CONFIG["base_url"]:
        issues.append("ATERA base URL not configured")

    # Validate timeouts
    if ATERA_CONFIG["timeout"] <= 0:
        issues.append("Invalid API timeout (must be positive)")

    # Validate priority threshold
    if TICKET_MANAGEMENT_CONFIG["voice_priority_threshold"] not in PRIORITY_VOICE_MAPPING:
        issues.append("Invalid voice priority threshold")

    return issues

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_voice_template(template_type: str, template_key: str = None) -> str:
    """
    Get voice template with fallback handling.

    Args:
        template_type: Type of template (e.g., 'ticket_status')
        template_key: Specific template key (e.g., 'open')

    Returns:
        Template string or fallback message
    """
    try:
        if template_key:
            return VOICE_TEMPLATES[template_type][template_key]
        else:
            templates = VOICE_TEMPLATES[template_type]
            if isinstance(templates, list):
                return templates[0]  # Return first template
            else:
                return str(templates)
    except KeyError:
        return "I'm having trouble accessing that information right now."

def format_voice_response(template: str, **kwargs) -> str:
    """
    Format voice response template with provided parameters.

    Args:
        template: Template string with placeholders
        **kwargs: Values to substitute in template

    Returns:
        Formatted voice response string
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing template parameter: {e}")
        return template  # Return unformatted template as fallback

if __name__ == "__main__":
    # Configuration validation and testing
    print("NETOVO VoiceBot ATERA Configuration")
    print("=" * 40)

    print(f"Environment: {ATERA_CONFIG['environment']}")
    print(f"Debug mode: {ATERA_CONFIG['debug_mode']}")
    print(f"API URL: {ATERA_CONFIG['base_url']}")
    print(f"API Key configured: {'Yes' if ATERA_CONFIG['api_key'] != 'your_atera_api_key_here' else 'No'}")

    # Validate configuration
    issues = validate_config()
    if issues:
        print("\nConfiguration Issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nConfiguration validation: PASSED")

    # Show voice template sample
    sample_template = get_voice_template("no_tickets")
    print(f"\nSample voice template: {sample_template}")
