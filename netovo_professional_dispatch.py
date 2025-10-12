#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
NETOVO Professional Dispatch Handler
Replaces human dispatch operations with AI following NETOVO's exact procedures.

This is the main dispatch system that coordinates:
- Customer intake and verification
- Urgency evaluation using NETOVO matrix
- Specialist routing and assignment
- ATERA ticket creation with all required fields
- Escalation timing and management
- Professional dispatch language and responses
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

# Import NETOVO configurations and components
try:
    from netovo_dispatch_config import (
        URGENCY_MATRIX, SPECIALIST_ROUTING, CONTRACT_TYPES, PRODUCT_FAMILIES,
        DISPATCH_RESPONSES, ESCALATION_PROCEDURES, BUSINESS_RULES,
        evaluate_urgency, determine_specialist, categorize_product_family,
        calculate_sla_response_time, format_dispatch_response
    )
    from atera_client import ATERAClient
    DISPATCH_CONFIG_AVAILABLE = True
except ImportError as e:
    logging.warning(f"NETOVO dispatch configuration not available: {e}")
    DISPATCH_CONFIG_AVAILABLE = False

logger = logging.getLogger(__name__)

class NETOVOProfessionalDispatch:
    """
    Professional AI Dispatch System for NETOVO following official procedures.

    This system replaces human dispatch operations with AI that follows
    NETOVO's exact business procedures for intake, urgency evaluation,
    specialist routing, and escalation management.
    """

    def __init__(self, atera_client: ATERAClient = None):
        """Initialize the professional dispatch system."""
        self.atera_client = atera_client or (ATERAClient() if ATERAClient else None)

        # Dispatch session state
        self.current_customer = None
        self.current_session = {}
        self.conversation_transcript = []
        self.escalation_timers = {}

        # Professional dispatch tracking
        self.information_gathered = {
            "issue_description": None,
            "scope_assessment": None,
            "impact_evaluation": None,
            "urgency_classification": None,
            "customer_verified": False
        }

        logger.info("NETOVO Professional Dispatch System initialized")

    def handle_customer_call(self, caller_phone: str, initial_input: str = None) -> Dict:
        """
        Handle incoming customer call with professional dispatch intake.

        Args:
            caller_phone: Customer's phone number for identification
            initial_input: Customer's initial statement (optional)

        Returns:
            Dispatch response with next actions
        """
        try:
            # Reset session for new call
            self._reset_session()

            # Professional greeting
            greeting = format_dispatch_response("greeting")

            # Attempt customer identification
            customer_lookup_result = self._identify_customer(caller_phone)

            # Start conversation transcript
            self.conversation_transcript.append({
                "timestamp": datetime.now().isoformat(),
                "speaker": "dispatch",
                "message": greeting,
                "action": "greeting"
            })

            response = {
                "dispatch_active": True,
                "voice_response": greeting,
                "voice_type": "professional",
                "customer_identified": customer_lookup_result.get("identified", False),
                "customer_data": customer_lookup_result.get("customer"),
                "next_action": "collect_issue_description",
                "session_id": self._generate_session_id(),
                "requires_input": True
            }

            # If customer provided initial input, process it
            if initial_input:
                follow_up = self.process_customer_input(initial_input)
                response.update(follow_up)

            return response

        except Exception as e:
            logger.error(f"Error in customer call handling: {e}")
            return self._generate_error_response("system_error")

    def process_customer_input(self, user_input: str, context: Dict = None) -> Dict:
        """
        Process customer input through professional dispatch workflow.

        Args:
            user_input: Customer's spoken input
            context: Additional conversation context

        Returns:
            Dispatch response with actions and next steps
        """
        try:
            # Record customer input
            self.conversation_transcript.append({
                "timestamp": datetime.now().isoformat(),
                "speaker": "customer",
                "message": user_input,
                "context": context or {}
            })

            # Determine current dispatch stage
            current_stage = self._determine_dispatch_stage()

            # Route to appropriate handler
            if current_stage == "customer_verification":
                return self._handle_customer_verification(user_input)
            elif current_stage == "issue_collection":
                return self._handle_issue_collection(user_input)
            elif current_stage == "scope_assessment":
                return self._handle_scope_assessment(user_input)
            elif current_stage == "urgency_evaluation":
                return self._handle_urgency_evaluation(user_input)
            elif current_stage == "ticket_creation":
                return self._handle_ticket_creation()
            else:
                # Default: start with issue collection
                return self._handle_issue_collection(user_input)

        except Exception as e:
            logger.error(f"Error processing customer input: {e}")
            return self._generate_error_response("processing_error")

    def _identify_customer(self, caller_phone: str) -> Dict:
        """Identify customer using ATERA lookup."""
        try:
            if not self.atera_client:
                return {"identified": False, "method": "no_atera"}

            customer = self.atera_client.search_customer_by_phone(caller_phone)

            if customer:
                self.current_customer = customer
                self.information_gathered["customer_verified"] = True

                logger.info(f"Customer identified: {customer.get('name', 'Unknown')}")
                return {
                    "identified": True,
                    "customer": customer,
                    "method": "phone_lookup",
                    "confidence": "high"
                }
            else:
                logger.info(f"No customer found for phone: {caller_phone}")
                return {
                    "identified": False,
                    "method": "phone_lookup_failed",
                    "requires_manual_verification": True
                }

        except Exception as e:
            logger.error(f"Customer identification error: {e}")
            return {"identified": False, "method": "error", "error": str(e)}

    def _handle_customer_verification(self, user_input: str) -> Dict:
        """Handle customer verification process."""
        try:
            # Check if customer is providing company name
            if not self.current_customer:
                return self._process_manual_customer_lookup(user_input)
            else:
                # Customer already identified, proceed to issue collection
                return self._transition_to_issue_collection()

        except Exception as e:
            logger.error(f"Customer verification error: {e}")
            return self._generate_error_response("verification_error")

    def _process_manual_customer_lookup(self, company_name: str) -> Dict:
        """Process manual customer lookup by company name."""
        try:
            if not self.atera_client:
                return self._generate_error_response("no_atera_access")

            customers = self.atera_client.get_customers(search_term=company_name, limit=5)

            if not customers:
                return {
                    "voice_response": f"I couldn't find a customer account for {company_name}. Could you spell that differently or provide your account number?",
                    "voice_type": "helping",
                    "next_action": "retry_customer_lookup",
                    "requires_input": True
                }
            elif len(customers) == 1:
                self.current_customer = customers[0]
                self.information_gathered["customer_verified"] = True

                return {
                    "voice_response": f"Thank you, I found your account for {customers[0]['voice_name']}. Now, what technical issue can I help you with today?",
                    "voice_type": "professional",
                    "customer_verified": True,
                    "customer_data": customers[0],
                    "next_action": "collect_issue_description",
                    "requires_input": True
                }
            else:
                # Multiple matches - need clarification
                names = [c['voice_name'] for c in customers[:3]]
                name_list = ", ".join(names[:-1]) + f", or {names[-1]}" if len(names) > 1 else names[0]

                return {
                    "voice_response": f"I found multiple companies with that name: {name_list}. Which one is correct?",
                    "voice_type": "clarifying",
                    "multiple_matches": customers,
                    "next_action": "clarify_customer_match",
                    "requires_input": True
                }

        except Exception as e:
            logger.error(f"Manual customer lookup error: {e}")
            return self._generate_error_response("lookup_error")

    def _handle_issue_collection(self, user_input: str) -> Dict:
        """Handle technical issue description collection."""
        try:
            # Store issue description
            self.information_gathered["issue_description"] = user_input

            # Ask scope assessment question
            scope_question = format_dispatch_response("information_gathering.scope_assessment")

            self.conversation_transcript.append({
                "timestamp": datetime.now().isoformat(),
                "speaker": "dispatch",
                "message": scope_question,
                "action": "scope_assessment"
            })

            return {
                "voice_response": scope_question,
                "voice_type": "professional",
                "next_action": "assess_scope",
                "requires_input": True,
                "stage": "scope_assessment"
            }

        except Exception as e:
            logger.error(f"Issue collection error: {e}")
            return self._generate_error_response("collection_error")

    def _handle_scope_assessment(self, user_input: str) -> Dict:
        """Handle scope and impact assessment."""
        try:
            # Store scope information
            self.information_gathered["scope_assessment"] = user_input

            # Ask impact assessment question
            impact_question = format_dispatch_response("information_gathering.impact")

            self.conversation_transcript.append({
                "timestamp": datetime.now().isoformat(),
                "speaker": "dispatch",
                "message": impact_question,
                "action": "impact_assessment"
            })

            return {
                "voice_response": impact_question,
                "voice_type": "professional",
                "next_action": "evaluate_urgency",
                "requires_input": True,
                "stage": "impact_assessment"
            }

        except Exception as e:
            logger.error(f"Scope assessment error: {e}")
            return self._generate_error_response("assessment_error")

    def _handle_urgency_evaluation(self, user_input: str) -> Dict:
        """Handle urgency evaluation and routing decision."""
        try:
            # Store impact information
            self.information_gathered["impact_evaluation"] = user_input

            # Combine all information for urgency evaluation
            issue_description = self.information_gathered["issue_description"]
            scope_info = self.information_gathered["scope_assessment"]
            impact_info = self.information_gathered["impact_evaluation"]

            # Evaluate urgency using NETOVO matrix
            full_description = f"{issue_description} {scope_info} {impact_info}"
            urgency_level, evaluation_details = evaluate_urgency(full_description, self.information_gathered)

            self.information_gathered["urgency_classification"] = urgency_level

            logger.info(f"Urgency evaluation: {urgency_level} - {evaluation_details['reasoning']}")

            # Route based on urgency
            if urgency_level in ["critical", "high"]:
                return self._handle_urgent_routing(urgency_level, evaluation_details)
            else:
                return self._handle_standard_routing(urgency_level, evaluation_details)

        except Exception as e:
            logger.error(f"Urgency evaluation error: {e}")
            return self._generate_error_response("evaluation_error")

    def _handle_urgent_routing(self, urgency_level: str, evaluation_details: Dict) -> Dict:
        """Handle urgent issue routing with immediate specialist assignment."""
        try:
            issue_description = self.information_gathered["issue_description"]

            # Determine specialist
            specialist = determine_specialist(issue_description, urgency_level)

            # Create NETOVO-compliant ticket
            ticket_result = self._create_netovo_ticket(
                urgency_level=urgency_level,
                specialist_assignment=specialist,
                is_urgent=True
            )

            if ticket_result["success"]:
                # Generate urgent response
                if urgency_level == "critical":
                    response_template = "critical_response.acknowledgment"
                else:
                    response_template = "critical_response.acknowledgment"

                acknowledgment = format_dispatch_response(response_template)

                ticket_info = format_dispatch_response(
                    "critical_response.ticket_creation",
                    ticket_id=ticket_result["ticket_id"],
                    specialist_type=specialist.replace("_", " ") if specialist else "technical specialist"
                )

                transfer_message = format_dispatch_response(
                    "critical_response.transfer",
                    specialist_name=specialist.replace("_", " ") if specialist else "technical specialist"
                )

                full_response = f"{acknowledgment} {ticket_info} {transfer_message}"

                return {
                    "voice_response": full_response,
                    "voice_type": "urgent",
                    "ticket_created": True,
                    "ticket_id": ticket_result["ticket_id"],
                    "urgency_level": urgency_level,
                    "specialist_assigned": specialist,
                    "requires_immediate_transfer": True,
                    "transfer_target": specialist,
                    "call_completed": True,
                    "netovo_compliant": True
                }
            else:
                # Ticket creation failed - escalate immediately
                return {
                    "voice_response": "I'm experiencing technical difficulties with our support system. Let me transfer you immediately to our technical manager for urgent assistance.",
                    "voice_type": "urgent",
                    "requires_immediate_escalation": True,
                    "escalation_reason": "system_failure",
                    "call_completed": True
                }

        except Exception as e:
            logger.error(f"Urgent routing error: {e}")
            return self._generate_error_response("urgent_routing_error")

    def _handle_standard_routing(self, urgency_level: str, evaluation_details: Dict) -> Dict:
        """Handle standard issue routing with queue placement."""
        try:
            # Create NETOVO-compliant ticket
            ticket_result = self._create_netovo_ticket(
                urgency_level=urgency_level,
                specialist_assignment=None,  # Unassigned per NETOVO procedure
                is_urgent=False
            )

            if ticket_result["success"]:
                # Generate standard response
                ticket_confirmation = format_dispatch_response(
                    "standard_response.ticket_creation",
                    ticket_id=ticket_result["ticket_id"],
                    issue_description=self.information_gathered["issue_description"]
                )

                sla_notification = format_dispatch_response(
                    "standard_response.sla_notification",
                    response_time=ticket_result["sla_target"]
                )

                follow_up = format_dispatch_response("standard_response.follow_up")

                full_response = f"{ticket_confirmation} {sla_notification} {follow_up}"

                # Start 15-minute escalation timer
                self._start_escalation_timer(ticket_result["ticket_id"])

                return {
                    "voice_response": full_response,
                    "voice_type": "professional",
                    "ticket_created": True,
                    "ticket_id": ticket_result["ticket_id"],
                    "urgency_level": urgency_level,
                    "sla_target": ticket_result["sla_target"],
                    "escalation_timer_started": True,
                    "requires_input": True,  # Ask if anything else needed
                    "next_action": "additional_assistance"
                }
            else:
                # Ticket creation failed
                return {
                    "voice_response": "I encountered an issue creating your support ticket. Let me transfer you to our technical support team for immediate assistance.",
                    "voice_type": "helping",
                    "requires_escalation": True,
                    "escalation_reason": "ticket_creation_failed"
                }

        except Exception as e:
            logger.error(f"Standard routing error: {e}")
            return self._generate_error_response("standard_routing_error")

    def _create_netovo_ticket(self, urgency_level: str, specialist_assignment: str = None, is_urgent: bool = False) -> Dict:
        """Create NETOVO-compliant ticket with all required fields."""
        try:
            if not self.current_customer:
                raise Exception("No customer identified for ticket creation")

            if not self.atera_client:
                raise Exception("ATERA client not available")

            # Extract information for ticket
            issue_description = self.information_gathered["issue_description"]

            # Map urgency to NETOVO priority
            priority_mapping = {
                "critical": "Critical",
                "high": "High",
                "medium": "Medium",
                "low": "Low"
            }
            priority = priority_mapping.get(urgency_level, "Medium")

            # Determine product family
            product_family = categorize_product_family(issue_description)

            # Get customer contract (default to standard if not available)
            contract_type = getattr(self.current_customer, 'contract_type', 'managed_services_standard')

            # Format title
            title = f"{issue_description[:50]}{'...' if len(issue_description) > 50 else ''}"

            # Create conversation transcript
            transcript = "\n".join([
                f"[{entry['timestamp']}] {entry['speaker']}: {entry['message']}"
                for entry in self.conversation_transcript
            ])

            # Internal notes
            internal_notes = f"""
NETOVO DISPATCH EVALUATION:
- Urgency Level: {urgency_level.upper()}
- Scope: {self.information_gathered.get('scope_assessment', 'Not assessed')}
- Impact: {self.information_gathered.get('impact_evaluation', 'Not assessed')}
- Specialist Required: {'Yes' if is_urgent else 'No'}
- Customer Verified: {self.information_gathered.get('customer_verified', False)}
            """.strip()

            # Create ticket using NETOVO method
            result = self.atera_client.create_ticket_netovo(
                customer_id=self.current_customer['id'],
                title=title,
                description=issue_description,
                priority=priority,
                urgency=priority,
                severity=urgency_level,
                product_family=product_family,
                contract_type=contract_type,
                internal_notes=internal_notes,
                specialist_assignment=specialist_assignment,
                escalation_time=15,  # NETOVO 15-minute rule
                customer_phone=getattr(self.current_customer, 'phone', ''),
                conversation_transcript=transcript
            )

            logger.info(f"NETOVO ticket creation result: {result.get('message', 'Unknown')}")
            return result

        except Exception as e:
            logger.error(f"NETOVO ticket creation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "voice_response": "I'm unable to create a ticket right now. Let me transfer you to our support team."
            }

    def _start_escalation_timer(self, ticket_id: str):
        """Start 15-minute escalation timer for NETOVO procedure."""
        try:
            escalation_time = datetime.now() + timedelta(minutes=15)
            self.escalation_timers[ticket_id] = {
                "ticket_id": ticket_id,
                "escalation_time": escalation_time,
                "status": "active",
                "customer_id": self.current_customer['id'] if self.current_customer else None
            }
            logger.info(f"Started 15-minute escalation timer for ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Error starting escalation timer: {e}")

    def _determine_dispatch_stage(self) -> str:
        """Determine current stage in dispatch workflow."""
        if not self.information_gathered.get("customer_verified"):
            return "customer_verification"
        elif not self.information_gathered.get("issue_description"):
            return "issue_collection"
        elif not self.information_gathered.get("scope_assessment"):
            return "scope_assessment"
        elif not self.information_gathered.get("urgency_classification"):
            return "urgency_evaluation"
        else:
            return "ticket_creation"

    def _generate_session_id(self) -> str:
        """Generate unique session ID for dispatch tracking."""
        return f"dispatch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self) % 10000}"

    def _reset_session(self):
        """Reset dispatch session for new call."""
        self.current_customer = None
        self.conversation_transcript = []
        self.information_gathered = {
            "issue_description": None,
            "scope_assessment": None,
            "impact_evaluation": None,
            "urgency_classification": None,
            "customer_verified": False
        }

    def _generate_error_response(self, error_type: str) -> Dict:
        """Generate appropriate error response for dispatch failures."""
        error_responses = {
            "system_error": "I'm experiencing technical difficulties. Let me transfer you to our support team.",
            "processing_error": "I encountered an issue processing your request. Let me connect you with technical support.",
            "verification_error": "I'm having trouble verifying your account. Let me transfer you to customer service.",
            "urgent_routing_error": "Due to the critical nature of your issue, I'm transferring you immediately to our technical manager.",
            "no_atera_access": "I'm unable to access our support system. Let me transfer you directly to our technical team."
        }

        return {
            "voice_response": error_responses.get(error_type, "Let me transfer you to our support team for assistance."),
            "voice_type": "empathetic",
            "error": True,
            "error_type": error_type,
            "requires_escalation": True,
            "call_completed": True
        }

if __name__ == "__main__":
    # Test the professional dispatch system
    print("NETOVO Professional Dispatch System Test")
    print("=" * 50)

    if DISPATCH_CONFIG_AVAILABLE:
        dispatch = NETOVOProfessionalDispatch()

        # Test urgency evaluation
        test_issues = [
            "Our entire email server is down and nobody can work",
            "My computer is running slow today",
            "The main file server crashed for everyone",
            "I need help setting up a new printer"
        ]

        for issue in test_issues:
            print(f"\nTesting: {issue}")
            urgency, details = evaluate_urgency(issue, {})
            specialist = determine_specialist(issue, urgency)
            print(f"Urgency: {urgency.upper()}")
            print(f"Specialist: {specialist or 'Queue Assignment'}")
            print(f"Reasoning: {details['reasoning']}")
    else:
        print("❌ Dispatch configuration not available")
