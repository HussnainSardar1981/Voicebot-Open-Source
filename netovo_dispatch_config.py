#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
NETOVO Professional Dispatch Configuration
Based on official NETOVO procedures and business requirements

This module contains all NETOVO-specific dispatch logic, urgency matrices,
escalation procedures, and business rules for the AI dispatch system.
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# NETOVO URGENCY EVALUATION MATRIX
# =============================================================================

URGENCY_MATRIX = {
    "critical": {
        "keywords": [
            "down", "outage", "crashed", "emergency", "critical", "urgent",
            "can't work", "production stopped", "business impact", "revenue impact",
            "servers down", "network down", "entire office", "all users",
            "system failure", "complete outage", "emergency situation"
        ],
        "scope_indicators": [
            "production", "all users", "entire office", "company wide",
            "everyone", "multiple departments", "critical system"
        ],
        "system_types": [
            "server", "network", "domain controller", "exchange server",
            "file server", "database", "internet", "phone system"
        ],
        "response_time": "immediate",
        "escalation_minutes": 5,
        "requires_specialist": True,
        "severity": "Critical",
        "priority": "Critical"
    },

    "high": {
        "keywords": [
            "slow", "intermittent", "affecting multiple", "important",
            "several users", "department down", "partial outage",
            "reduced functionality", "significant impact"
        ],
        "scope_indicators": [
            "department", "several users", "multiple people",
            "important system", "shared resource"
        ],
        "system_types": [
            "shared drive", "printer", "application server",
            "departmental system", "backup system"
        ],
        "response_time": "within 4 hours",
        "escalation_minutes": 15,
        "requires_specialist": False,
        "severity": "High",
        "priority": "High"
    },

    "medium": {
        "keywords": [
            "single user", "minor issue", "individual problem",
            "one computer", "personal device", "not urgent"
        ],
        "scope_indicators": [
            "just me", "one person", "individual", "single computer",
            "my laptop", "personal issue"
        ],
        "system_types": [
            "desktop", "laptop", "individual software",
            "personal email", "local application"
        ],
        "response_time": "within 8 hours",
        "escalation_minutes": 30,
        "requires_specialist": False,
        "severity": "Medium",
        "priority": "Medium"
    },

    "low": {
        "keywords": [
            "training", "enhancement", "improvement", "when convenient",
            "low priority", "future", "optimization", "upgrade request",
            "nice to have", "when time permits"
        ],
        "scope_indicators": [
            "future planning", "optimization", "training request",
            "non-essential", "enhancement"
        ],
        "system_types": [
            "training", "consultation", "future upgrade",
            "non-essential feature", "optimization"
        ],
        "response_time": "within 24 hours",
        "escalation_minutes": 60,
        "requires_specialist": False,
        "severity": "Low",
        "priority": "Low"
    }
}

# =============================================================================
# NETOVO SPECIALIST ROUTING MATRIX
# =============================================================================

SPECIALIST_ROUTING = {
    "senior_network_technician": {
        "keywords": [
            "network", "internet", "connectivity", "router", "switch",
            "firewall", "vpn", "wifi", "wireless", "bandwidth",
            "ip address", "dns", "dhcp", "network drive"
        ],
        "issue_types": ["network_infrastructure", "connectivity", "internet"],
        "escalation_time": 5,  # minutes for critical network issues
        "contact_method": "immediate_phone",
        "atera_assignment": "network_specialist"
    },

    "systems_administrator": {
        "keywords": [
            "server", "domain", "active directory", "file server",
            "database", "backup", "domain controller", "group policy",
            "windows server", "linux server", "virtual machine"
        ],
        "issue_types": ["server_systems", "domain_services", "backup"],
        "escalation_time": 10,
        "contact_method": "phone_then_teams",
        "atera_assignment": "systems_admin"
    },

    "exchange_specialist": {
        "keywords": [
            "email", "outlook", "exchange", "calendar", "contacts",
            "distribution list", "mailbox", "email server", "office 365"
        ],
        "issue_types": ["email_systems", "exchange", "office365"],
        "escalation_time": 15,
        "contact_method": "teams_then_phone",
        "atera_assignment": "email_specialist"
    },

    "field_technician": {
        "keywords": [
            "computer", "laptop", "desktop", "software", "application",
            "printer", "local issue", "individual computer", "workstation"
        ],
        "issue_types": ["desktop_support", "applications", "hardware"],
        "escalation_time": 30,
        "contact_method": "teams_notification",
        "atera_assignment": "field_tech"
    }
}

# =============================================================================
# NETOVO CONTRACT AND SLA DEFINITIONS
# =============================================================================

CONTRACT_TYPES = {
    "managed_services_premium": {
        "contract_name": "Managed Services Premium",
        "sla_response_times": {
            "Critical": "1 hour",
            "High": "4 hours",
            "Medium": "8 hours",
            "Low": "24 hours"
        },
        "business_hours": "24/7",
        "after_hours_support": True,
        "escalation_matrix": "premium"
    },

    "managed_services_standard": {
        "contract_name": "Managed Services Standard",
        "sla_response_times": {
            "Critical": "2 hours",
            "High": "8 hours",
            "Medium": "24 hours",
            "Low": "72 hours"
        },
        "business_hours": "8AM-6PM Mon-Fri",
        "after_hours_support": False,
        "escalation_matrix": "standard"
    },

    "break_fix": {
        "contract_name": "Break/Fix Support",
        "sla_response_times": {
            "Critical": "4 hours",
            "High": "24 hours",
            "Medium": "72 hours",
            "Low": "1 week"
        },
        "business_hours": "8AM-5PM Mon-Fri",
        "after_hours_support": False,
        "escalation_matrix": "basic"
    }
}

# =============================================================================
# NETOVO PRODUCT FAMILY CATEGORIZATION
# =============================================================================

PRODUCT_FAMILIES = {
    "Network Infrastructure": [
        "network", "internet", "connectivity", "router", "switch",
        "firewall", "vpn", "wifi", "bandwidth"
    ],

    "Server Systems": [
        "server", "domain", "active directory", "file server",
        "database", "backup", "virtual machine"
    ],

    "Email & Communication": [
        "email", "outlook", "exchange", "calendar", "contacts",
        "office 365", "teams", "phone system"
    ],

    "Desktop & Applications": [
        "computer", "laptop", "desktop", "software", "application",
        "windows", "microsoft office", "printer"
    ],

    "Security & Compliance": [
        "antivirus", "security", "firewall", "compliance",
        "backup", "data protection", "encryption"
    ],

    "Cloud Services": [
        "office 365", "azure", "cloud", "onedrive",
        "sharepoint", "online services"
    ]
}

# =============================================================================
# PROFESSIONAL DISPATCH LANGUAGE TEMPLATES
# =============================================================================

DISPATCH_RESPONSES = {
    "greeting": [
        "Good {time_of_day}, you've reached Netovo technical support. This is Alexis, your AI dispatch assistant. What technical issue can I help you with today?",
        "Thank you for calling Netovo technical support. I'm Alexis, and I'll be handling your support request today. How can I assist you?",
        "Good {time_of_day}, this is Alexis from Netovo technical support. What technical issue are you experiencing?"
    ],

    "information_gathering": {
        "issue_description": "Can you describe the technical issue you're experiencing in detail?",
        "scope_assessment": "Is this affecting just you, or are other people in your office experiencing this as well?",
        "timing": "When did this issue first start occurring?",
        "impact": "Is this preventing you from working, or are you able to work around it?",
        "system_type": "Is this related to your computer, email, network, or server systems?"
    },

    "customer_verification": {
        "phone_match": "I have your number associated with {company_name}. Is that correct?",
        "manual_lookup": "What company are you calling from so I can locate your account?",
        "confirmation": "Thank you, I found your account for {company_name}. Let me document your technical issue."
    },

    "critical_response": {
        "acknowledgment": "I understand this is a critical issue affecting your business operations.",
        "ticket_creation": "I'm creating an urgent priority ticket number {ticket_id} and transferring you immediately to our {specialist_type}.",
        "transfer": "Please hold while I connect you with {specialist_name} who will take immediate ownership of this issue."
    },

    "standard_response": {
        "ticket_creation": "I've created ticket number {ticket_id} for your {issue_description}.",
        "sla_notification": "Based on your service agreement, our technical team will contact you within {response_time}.",
        "confirmation": "You'll receive an email confirmation with your ticket details shortly.",
        "follow_up": "Is there anything else I can help you with today?"
    },

    "escalation_language": {
        "immediate": "Due to the critical nature of this issue, I'm escalating this immediately to our senior technical team.",
        "specialist_unavailable": "Your assigned specialist is temporarily unavailable. I'm escalating this to our technical manager for immediate attention.",
        "system_failure": "I'm experiencing difficulty accessing our support system. Let me transfer you directly to our technical support team."
    }
}

# =============================================================================
# ESCALATION TIMING AND PROCEDURES
# =============================================================================

ESCALATION_PROCEDURES = {
    "15_minute_rule": {
        "initial_check": 15,  # minutes
        "technician_ping": 30,  # total minutes (15 + 15)
        "manager_escalation": 45,  # total minutes (15 + 15 + 15)
        "executive_escalation": 90  # total minutes for critical issues
    },

    "notification_methods": {
        "technician": ["teams", "email", "sms_if_urgent"],
        "manager": ["phone", "teams", "email"],
        "executive": ["phone", "sms", "teams"]
    },

    "escalation_triggers": {
        "unassigned_ticket": "15 minutes",
        "no_technician_response": "30 minutes",
        "critical_unresolved": "45 minutes",
        "sla_breach_imminent": "80% of SLA time"
    }
}

# =============================================================================
# NETOVO BUSINESS RULES AND VALIDATION
# =============================================================================

BUSINESS_RULES = {
    "ticket_requirements": {
        "mandatory_fields": [
            "severity", "product_family", "internal_notes",
            "contract", "customer_verified", "impact_assessment"
        ],
        "field_technician_assignment": "unassigned_unless_urgent",
        "response_time_calculation": "based_on_contract_and_priority",
        "escalation_tracking": "required_for_all_tickets"
    },

    "customer_verification": {
        "phone_lookup": "attempt_automatic_first",
        "manual_verification": "required_if_not_found",
        "company_confirmation": "always_verify_company_name",
        "multiple_matches": "require_clarification"
    },

    "priority_override": {
        "business_impact": "can_elevate_priority",
        "vip_customers": "expedited_handling",
        "after_hours": "different_escalation_matrix",
        "holiday_schedule": "emergency_only_routing"
    }
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def evaluate_urgency(issue_description: str, customer_responses: Dict) -> Tuple[str, Dict]:
    """
    Evaluate issue urgency using NETOVO's urgency matrix.

    Args:
        issue_description: Description of the technical issue
        customer_responses: Customer responses to assessment questions

    Returns:
        Tuple of (urgency_level, evaluation_details)
    """
    issue_lower = issue_description.lower()

    # Check each urgency level (highest to lowest)
    for urgency_level, criteria in URGENCY_MATRIX.items():
        score = 0
        matches = []

        # Check keywords
        keyword_matches = [kw for kw in criteria["keywords"] if kw in issue_lower]
        if keyword_matches:
            score += len(keyword_matches) * 3
            matches.extend(keyword_matches)

        # Check scope indicators
        scope_matches = [si for si in criteria["scope_indicators"] if si in issue_lower]
        if scope_matches:
            score += len(scope_matches) * 2
            matches.extend(scope_matches)

        # Check system types
        system_matches = [st for st in criteria["system_types"] if st in issue_lower]
        if system_matches:
            score += len(system_matches) * 2
            matches.extend(system_matches)

        # If we have matches and meet threshold, return this urgency level
        if score >= 3:  # Threshold for urgency classification
            return urgency_level, {
                "score": score,
                "matches": matches,
                "criteria": criteria,
                "reasoning": f"Matched {len(matches)} indicators for {urgency_level} urgency"
            }

    # Default to medium if no clear match
    return "medium", {
        "score": 0,
        "matches": [],
        "criteria": URGENCY_MATRIX["medium"],
        "reasoning": "Default classification - no clear urgency indicators"
    }

def determine_specialist(issue_description: str, urgency_level: str) -> Optional[str]:
    """
    Determine the appropriate specialist for the issue.

    Args:
        issue_description: Description of the technical issue
        urgency_level: Urgency level from evaluation

    Returns:
        Specialist type or None for queue assignment
    """
    if urgency_level not in ["critical", "high"]:
        return None  # Non-urgent goes to queue per NETOVO procedure

    issue_lower = issue_description.lower()
    best_match = None
    best_score = 0

    for specialist, criteria in SPECIALIST_ROUTING.items():
        score = sum(1 for keyword in criteria["keywords"] if keyword in issue_lower)
        if score > best_score:
            best_score = score
            best_match = specialist

    return best_match

def categorize_product_family(issue_description: str) -> str:
    """
    Categorize the issue into a NETOVO product family.

    Args:
        issue_description: Description of the technical issue

    Returns:
        Product family name
    """
    issue_lower = issue_description.lower()

    for family, keywords in PRODUCT_FAMILIES.items():
        if any(keyword in issue_lower for keyword in keywords):
            return family

    return "Desktop & Applications"  # Default category

def calculate_sla_response_time(contract_type: str, priority: str) -> str:
    """
    Calculate SLA response time based on contract and priority.

    Args:
        contract_type: Customer's contract type
        priority: Issue priority level

    Returns:
        SLA response time string
    """
    if contract_type in CONTRACT_TYPES:
        return CONTRACT_TYPES[contract_type]["sla_response_times"].get(priority, "24 hours")

    return "24 hours"  # Default SLA

def format_dispatch_response(template_key: str, **kwargs) -> str:
    """
    Format a dispatch response template with provided parameters.

    Args:
        template_key: Key for the response template
        **kwargs: Parameters to substitute in template

    Returns:
        Formatted response string
    """
    try:
        if "." in template_key:
            category, specific = template_key.split(".", 1)
            template = DISPATCH_RESPONSES[category][specific]
        else:
            templates = DISPATCH_RESPONSES[template_key]
            template = templates[0] if isinstance(templates, list) else templates

        # Add time of day if not provided
        if "time_of_day" not in kwargs:
            hour = datetime.now().hour
            if hour < 12:
                kwargs["time_of_day"] = "morning"
            elif hour < 17:
                kwargs["time_of_day"] = "afternoon"
            else:
                kwargs["time_of_day"] = "evening"

        return template.format(**kwargs)

    except (KeyError, IndexError) as e:
        return "I'm ready to help you with your technical support request."

if __name__ == "__main__":
    # Test the urgency evaluation
    test_issues = [
        "Our entire network is down and nobody can work",
        "My computer is running a bit slow",
        "Email server crashed for the whole company",
        "Can you help me install new software?"
    ]

    print("NETOVO Dispatch Configuration Test")
    print("=" * 50)

    for issue in test_issues:
        urgency, details = evaluate_urgency(issue, {})
        specialist = determine_specialist(issue, urgency)
        product_family = categorize_product_family(issue)

        print(f"\nIssue: {issue}")
        print(f"Urgency: {urgency.upper()}")
        print(f"Specialist: {specialist or 'Queue Assignment'}")
        print(f"Product Family: {product_family}")
        print(f"Reasoning: {details['reasoning']}")
        print("-" * 30)
