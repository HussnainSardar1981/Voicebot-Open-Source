#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA API Client for NETOVO VoiceBot Integration

Purpose: Professional ATERA MSP platform integration for ticket management,
         customer service, and alert handling via natural voice interactions.

Key Features:
- Ticket CRUD operations (create, read, update, close)
- Customer lookup and validation
- Alert retrieval and management
- Device/agent status checking
- Voice-optimized response formatting
- Enterprise error handling and retry logic

This integrates with NETOVO's MSP workflow for Milestone 4 delivery.
"""

import requests
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import re

# Configuration
try:
    from atera_config import ATERA_CONFIG
except ImportError:
    # Fallback configuration
    ATERA_CONFIG = {
        "api_key": "your_api_key_here",
        "base_url": "https://app.atera.com/api/v3",
        "timeout": 15.0,
        "max_retries": 3,
        "rate_limit_delay": 1.0
    }

logger = logging.getLogger(__name__)

class ATERAClient:
    """
    Professional ATERA API client for MSP operations and VoiceBot integration.

    Features:
    - Complete ticket lifecycle management
    - Customer and contact management
    - Alert and device monitoring
    - Voice-friendly response formatting
    - Enterprise error handling
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize ATERA client with configuration."""
        self.config = config or ATERA_CONFIG
        self.base_url = self.config["base_url"]
        self.api_key = self.config["api_key"]
        self.timeout = self.config.get("timeout", 15.0)
        self.max_retries = self.config.get("max_retries", 3)
        self.rate_limit_delay = self.config.get("rate_limit_delay", 1.0)

        # Request tracking
        self.last_request_time = 0

        # Standard headers
        self.headers = {
            'X-API-KEY': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        logger.info(f"ATERAClient initialized for {self.base_url}")

    def _rate_limit(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """
        Make HTTP request to ATERA API with error handling and retries.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/tickets')
            data: Request body data
            params: URL parameters

        Returns:
            API response data

        Raises:
            Exception: On API errors or network failures
        """
        url = f"{self.base_url}{endpoint}"

        # Rate limiting
        self._rate_limit()

        # Make request with retries
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"ATERA API request: {method} {endpoint} (attempt {attempt + 1})")

                if method.upper() == 'GET':
                    response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=self.headers, json=data, params=params, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=self.headers, json=data, params=params, timeout=self.timeout)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, headers=self.headers, params=params, timeout=self.timeout)
                else:
                    raise Exception(f"Unsupported HTTP method: {method}")

                # Handle response
                if response.status_code in [200, 201, 202]:
                    logger.debug(f"ATERA API success: {method} {endpoint}")
                    return response.json() if response.content else {}

                elif response.status_code == 401:
                    raise Exception("ATERA authentication failed - check API key")

                elif response.status_code == 403:
                    raise Exception("ATERA access forbidden - insufficient permissions")

                elif response.status_code == 404:
                    raise Exception(f"ATERA endpoint not found: {endpoint}")

                elif response.status_code == 429:
                    # Rate limited - wait longer and retry
                    wait_time = 2 ** attempt
                    logger.warning(f"ATERA rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                else:
                    error_msg = f"ATERA API error: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_msg += f" - {error_data['message']}"
                    except:
                        pass
                    raise Exception(error_msg)

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"ATERA API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except Exception as e:
                last_exception = e
                logger.error(f"ATERA API error: {e}")
                break  # Don't retry on API errors

        # All retries failed
        raise Exception(f"ATERA API request failed after {self.max_retries} attempts: {last_exception}")

    def get_customers(self, search_term: str = None, limit: int = 50) -> List[Dict]:
        """
        Get customers with optional search filtering.

        Args:
            search_term: Optional search term for customer name
            limit: Maximum number of customers to return

        Returns:
            List of customer dictionaries with voice-ready information
        """
        try:
            params = {'itemsInPage': limit}
            if search_term:
                params['search'] = search_term

            response = self._make_request('GET', '/customers', params=params)

            customers = response.get('items', [])

            # Process customers for voice integration
            processed_customers = []
            for customer in customers:
                processed = self._process_customer_for_voice(customer)
                if processed:
                    processed_customers.append(processed)

            logger.info(f"Retrieved {len(processed_customers)} customers")
            return processed_customers

        except Exception as e:
            logger.error(f"Failed to get customers: {e}")
            return []

    def _process_customer_for_voice(self, customer: Dict) -> Optional[Dict]:
        """Process raw customer data for voice-friendly format."""
        try:
            return {
                "id": customer.get("CustomerID"),
                "name": customer.get("CustomerName", "Unknown Customer"),
                "voice_name": self._make_voice_friendly(customer.get("CustomerName", "")),
                "contact_person": customer.get("CustomerContactPerson", ""),
                "phone": customer.get("CustomerPhone", ""),
                "email": customer.get("CustomerEmail", ""),
                "status": customer.get("CustomerStatus", "Active"),
                "created_date": customer.get("CreatedOn", ""),
                "ticket_count": customer.get("TicketsCount", 0),
                "devices_count": customer.get("DevicesCount", 0)
            }
        except Exception as e:
            logger.error(f"Failed to process customer: {e}")
            return None

    def get_tickets(self, customer_id: int = None, status: str = None, limit: int = 50) -> List[Dict]:
        """
        Get tickets with optional filtering.

        Args:
            customer_id: Filter by specific customer
            status: Filter by ticket status (Open, Pending, Resolved, Closed)
            limit: Maximum number of tickets to return

        Returns:
            List of ticket dictionaries with voice-ready information
        """
        try:
            params = {'itemsInPage': limit}
            if customer_id:
                params['customerId'] = customer_id
            if status:
                params['ticketStatus'] = status

            response = self._make_request('GET', '/tickets', params=params)

            tickets = response.get('items', [])

            # Process tickets for voice integration
            processed_tickets = []
            for ticket in tickets:
                processed = self._process_ticket_for_voice(ticket)
                if processed:
                    processed_tickets.append(processed)

            logger.info(f"Retrieved {len(processed_tickets)} tickets")
            return processed_tickets

        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return []

    def _process_ticket_for_voice(self, ticket: Dict) -> Optional[Dict]:
        """Process raw ticket data for voice-friendly format."""
        try:
            # Calculate time ago
            created_date = ticket.get("TicketCreatedDate", "")
            time_ago = self._format_time_ago_from_string(created_date)

            return {
                "id": ticket.get("TicketID"),
                "title": ticket.get("TicketTitle", "Unknown Issue"),
                "voice_title": self._make_voice_friendly(ticket.get("TicketTitle", "")),
                "description": ticket.get("TicketDescription", ""),
                "status": ticket.get("TicketStatus", "Unknown"),
                "priority": ticket.get("TicketPriority", "Medium"),
                "customer_id": ticket.get("CustomerID"),
                "customer_name": ticket.get("CustomerBusinessName", ""),
                "technician": ticket.get("TechnicianFullName", "Unassigned"),
                "created_date": created_date,
                "time_ago": time_ago,
                "last_update": ticket.get("TicketLastUpdate", ""),
                "voice_summary": self._generate_ticket_voice_summary(ticket, time_ago)
            }
        except Exception as e:
            logger.error(f"Failed to process ticket: {e}")
            return None

    def create_ticket(self, customer_id: int, title: str, description: str,
                     priority: str = "Medium", urgency: str = "Medium") -> Dict:
        """
        Create a new support ticket.

        Args:
            customer_id: Customer ID for the ticket
            title: Ticket title/subject
            description: Detailed description of the issue
            priority: Ticket priority (Low, Medium, High, Critical)
            urgency: Ticket urgency (Low, Medium, High, Critical)

        Returns:
            Created ticket information or error details
        """
        try:
            ticket_data = {
                "CustomerID": customer_id,
                "TicketTitle": title,
                "TicketDescription": description,
                "TicketPriority": priority,
                "TicketUrgency": urgency,
                "TicketStatus": "Open",
                "Source": "VoiceBot API"
            }

            response = self._make_request('POST', '/tickets', data=ticket_data)

            if response and 'ActionID' in response:
                logger.info(f"Created ticket: {response['ActionID']}")
                return {
                    "success": True,
                    "ticket_id": response['ActionID'],
                    "message": f"Ticket {response['ActionID']} created successfully",
                    "voice_response": f"I've created ticket number {response['ActionID']} for {title}. It's been assigned {priority} priority."
                }
            else:
                logger.error(f"Unexpected ticket creation response: {response}")
                return {
                    "success": False,
                    "error": "Unexpected response format",
                    "voice_response": "I encountered an issue creating your ticket. Please try again or contact support directly."
                }

        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return {
                "success": False,
                "error": str(e),
                "voice_response": "I'm unable to create a ticket right now. Please try again or contact support directly."
            }

    def update_ticket_status(self, ticket_id: int, status: str, comment: str = None) -> Dict:
        """
        Update ticket status with optional comment.

        Args:
            ticket_id: Ticket ID to update
            status: New status (Open, Pending, Resolved, Closed)
            comment: Optional comment about the status change

        Returns:
            Update result information
        """
        try:
            update_data = {
                "TicketStatus": status
            }

            response = self._make_request('PUT', f'/tickets/{ticket_id}', data=update_data)

            # Add comment if provided
            if comment:
                comment_data = {
                    "Comment": comment,
                    "IsInternal": False
                }
                self._make_request('POST', f'/tickets/{ticket_id}/comments', data=comment_data)

            logger.info(f"Updated ticket {ticket_id} status to {status}")
            return {
                "success": True,
                "message": f"Ticket {ticket_id} status updated to {status}",
                "voice_response": f"Ticket {ticket_id} has been updated to {status} status."
            }

        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "voice_response": f"I couldn't update ticket {ticket_id}. Please try again."
            }

    def get_alerts(self, limit: int = 50) -> List[Dict]:
        """
        Get current alerts from ATERA monitoring.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries with voice-ready information
        """
        try:
            params = {'itemsInPage': limit}
            response = self._make_request('GET', '/alerts', params=params)

            alerts = response.get('items', [])

            # Process alerts for voice integration
            processed_alerts = []
            for alert in alerts:
                processed = self._process_alert_for_voice(alert)
                if processed:
                    processed_alerts.append(processed)

            logger.info(f"Retrieved {len(processed_alerts)} alerts")
            return processed_alerts

        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

    def _process_alert_for_voice(self, alert: Dict) -> Optional[Dict]:
        """Process raw alert data for voice-friendly format."""
        try:
            alert_time = alert.get("AlertTime", "")
            time_ago = self._format_time_ago_from_string(alert_time)

            return {
                "id": alert.get("AlertID"),
                "message": alert.get("AlertMessage", "Unknown alert"),
                "voice_message": self._make_voice_friendly(alert.get("AlertMessage", "")),
                "severity": alert.get("Severity", "Medium"),
                "device_name": alert.get("DeviceName", "Unknown device"),
                "customer_name": alert.get("CustomerName", ""),
                "alert_time": alert_time,
                "time_ago": time_ago,
                "resolved": alert.get("IsResolved", False),
                "voice_summary": f"{alert.get('Severity', 'Medium')} alert on {alert.get('DeviceName', 'device')}: {self._make_voice_friendly(alert.get('AlertMessage', 'Unknown issue'))}, detected {time_ago}"
            }
        except Exception as e:
            logger.error(f"Failed to process alert: {e}")
            return None

    def search_customer_by_phone(self, phone_number: str) -> Optional[Dict]:
        """
        Search for customer by phone number.

        Args:
            phone_number: Phone number to search for

        Returns:
            Customer information if found, None otherwise
        """
        try:
            # Clean phone number for searching
            clean_phone = re.sub(r'[^\d]', '', phone_number)

            customers = self.get_customers(limit=100)

            for customer in customers:
                customer_phone = re.sub(r'[^\d]', '', customer.get('phone', ''))
                if clean_phone in customer_phone or customer_phone in clean_phone:
                    logger.info(f"Found customer by phone: {customer['name']}")
                    return customer

            logger.info(f"No customer found for phone: {phone_number}")
            return None

        except Exception as e:
            logger.error(f"Failed to search customer by phone: {e}")
            return None

    def get_customer_ticket_summary(self, customer_id: int) -> Dict:
        """
        Get voice-optimized ticket summary for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            Voice-ready ticket summary
        """
        try:
            # Get customer info
            customers = self.get_customers()
            customer = next((c for c in customers if c['id'] == customer_id), None)

            if not customer:
                return {
                    "voice_summary": "I couldn't find that customer in our system.",
                    "ticket_count": 0
                }

            # Get tickets for customer
            tickets = self.get_tickets(customer_id=customer_id, limit=20)

            open_tickets = [t for t in tickets if t['status'] in ['Open', 'Pending']]
            closed_tickets = [t for t in tickets if t['status'] in ['Resolved', 'Closed']]

            # Generate voice summary
            if not tickets:
                voice_summary = f"{customer['voice_name']} has no support tickets."
            elif not open_tickets:
                voice_summary = f"{customer['voice_name']} has no open tickets. All {len(tickets)} tickets are resolved."
            elif len(open_tickets) == 1:
                ticket = open_tickets[0]
                voice_summary = f"{customer['voice_name']} has 1 open ticket: {ticket['voice_title']}, created {ticket['time_ago']}."
            else:
                voice_summary = f"{customer['voice_name']} has {len(open_tickets)} open tickets."
                if len(open_tickets) <= 3:
                    ticket_list = ", ".join([t['voice_title'] for t in open_tickets[:3]])
                    voice_summary += f" Issues include: {ticket_list}."

            return {
                "customer_name": customer['voice_name'],
                "total_tickets": len(tickets),
                "open_tickets": len(open_tickets),
                "closed_tickets": len(closed_tickets),
                "recent_tickets": tickets[:5],
                "voice_summary": voice_summary
            }

        except Exception as e:
            logger.error(f"Failed to get customer ticket summary: {e}")
            return {
                "voice_summary": "I'm unable to retrieve ticket information right now.",
                "ticket_count": 0
            }

    def _make_voice_friendly(self, text: str) -> str:
        """Convert technical text to voice-friendly format."""
        if not text:
            return ""

        # Replace common technical terms
        replacements = {
            "CPU": "C P U",
            "RAM": "R A M",
            "HDD": "hard drive",
            "SSD": "solid state drive",
            "SQL": "S Q L",
            "DNS": "D N S",
            "HTTP": "H T T P",
            "HTTPS": "H T T P S",
            "VPN": "V P N",
            "IP": "I P",
            "URL": "U R L",
            "API": "A P I",
            "&": " and ",
            "@": " at ",
            "_": " ",
            "-": " "
        }

        voice_text = text
        for old, new in replacements.items():
            voice_text = voice_text.replace(old, new)

        return voice_text

    def _format_time_ago_from_string(self, date_string: str) -> str:
        """Format time difference from date string in voice-friendly format."""
        if not date_string:
            return "unknown time"

        try:
            # Parse various date formats ATERA might use
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    date_obj = datetime.strptime(date_string.split('.')[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return "unknown time"

            now = datetime.now()
            diff = now - date_obj

            if diff.total_seconds() < 60:
                return "just now"
            elif diff.total_seconds() < 3600:
                minutes = int(diff.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = diff.days
                return f"{days} day{'s' if days != 1 else ''} ago"

        except Exception:
            return "unknown time"

    def _generate_ticket_voice_summary(self, ticket: Dict, time_ago: str) -> str:
        """Generate voice-optimized ticket summary."""
        title = self._make_voice_friendly(ticket.get("TicketTitle", "Unknown issue"))
        status = ticket.get("TicketStatus", "Unknown")
        priority = ticket.get("TicketPriority", "Medium")

        return f"{priority} priority ticket: {title}, status {status}, created {time_ago}"

    def test_connection(self) -> Dict:
        """
        Test ATERA API connection and return status.

        Returns:
            Dictionary with connection test results
        """
        try:
            # Test basic API access
            customers = self.get_customers(limit=1)

            return {
                "connected": True,
                "api_accessible": True,
                "customer_count": len(customers),
                "message": "ATERA connection successful",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"ATERA connection test failed: {e}")
            return {
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Compatibility alias for socket integration
SimpleATERAClient = ATERAClient

if __name__ == "__main__":
    # Test the client
    print("Testing ATERA Client...")

    client = ATERAClient()

    # Test connection
    connection_test = client.test_connection()
    print(f"Connection test: {connection_test}")

    if connection_test["connected"]:
        print("\nTesting customer lookup...")
        customers = client.get_customers(limit=3)
        print(f"Found {len(customers)} customers")

        if customers:
            customer = customers[0]
            print(f"Sample customer: {customer['voice_name']}")

            # Test ticket lookup
            print(f"\nGetting tickets for {customer['name']}...")
            tickets = client.get_tickets(customer_id=customer['id'], limit=5)
            print(f"Found {len(tickets)} tickets")

            # Test ticket summary
            summary = client.get_customer_ticket_summary(customer['id'])
            print(f"Voice summary: {summary['voice_summary']}")

        print("\nTesting alerts...")
        alerts = client.get_alerts(limit=3)
        print(f"Found {len(alerts)} alerts")

    print("ATERA client test completed.")