#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA Socket Client for NETOVO VoiceBot Integration

Purpose: Socket-based ATERA client proxy following the same pattern as socket_clients.py
         Provides zero-latency access to ATERA MSP operations via persistent service.

This module integrates with the existing model_warmup_service.py architecture
to provide instant ATERA responses without connection overhead.

Key Features:
- Drop-in replacement for direct ATERAClient
- Unix domain socket communication
- JSON request/response protocol
- Same API surface as direct client
- Health check integration
- Consistent error handling
"""

import socket
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ATERASocketClient:
    """
    Socket-based ATERA client proxy for instant MSP operations access.

    This client provides the same interface as the direct ATERAClient
    but communicates via Unix domain socket to the model warmup service
    for zero connection overhead.
    """

    def __init__(self, socket_path: str = "/tmp/netovo_atera.sock"):
        """Initialize socket client with connection path."""
        self.socket_path = socket_path
        self.buffer_size = 4096
        logger.info(f"ATERASocketClient initialized with socket: {socket_path}")

    def _send_request(self, action: str, **kwargs) -> Dict:
        """
        Send request to ATERA service via Unix socket.

        Args:
            action: Action to perform (get_customers, create_ticket, etc.)
            **kwargs: Additional parameters for the action

        Returns:
            Response dictionary from ATERA service

        Raises:
            Exception: On socket communication errors
        """
        try:
            # Prepare request
            request = {
                "action": action,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }

            # Connect to socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5.0)  # 5 second timeout

            try:
                sock.connect(self.socket_path)

                # Send request
                request_data = json.dumps(request).encode('utf-8')
                sock.sendall(request_data)

                # Receive response
                response_data = sock.recv(self.buffer_size)
                response = json.loads(response_data.decode('utf-8'))

                # Check for errors
                if response.get("status") == "error":
                    error_msg = response.get("message", "Unknown ATERA service error")
                    raise Exception(f"ATERA service error: {error_msg}")

                return response

            finally:
                sock.close()

        except FileNotFoundError:
            raise Exception(
                "ATERA service is not running. Please start the model warmup service "
                "with ATERA integration enabled."
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid response from ATERA service: {e}")
        except socket.timeout:
            raise Exception("ATERA service request timeout")
        except Exception as e:
            logger.error(f"ATERA socket communication error: {e}")
            raise

    def get_customers(self, search_term: str = None, limit: int = 50) -> List[Dict]:
        """
        Get customers via socket service.

        Args:
            search_term: Optional search term for customer name
            limit: Maximum number of customers to return

        Returns:
            List of customer dictionaries
        """
        try:
            response = self._send_request(
                "get_customers",
                search_term=search_term,
                limit=limit
            )

            return response.get("customers", [])

        except Exception as e:
            logger.error(f"Failed to get customers: {e}")
            return []

    def get_tickets(self, customer_id: int = None, status: str = None, limit: int = 50) -> List[Dict]:
        """
        Get tickets via socket service.

        Args:
            customer_id: Filter by specific customer
            status: Filter by ticket status
            limit: Maximum number of tickets to return

        Returns:
            List of ticket dictionaries
        """
        try:
            response = self._send_request(
                "get_tickets",
                customer_id=customer_id,
                status=status,
                limit=limit
            )

            return response.get("tickets", [])

        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return []

    def create_ticket(self, customer_id: int, title: str, description: str,
                     priority: str = "Medium", urgency: str = "Medium") -> Dict:
        """
        Create ticket via socket service.

        Args:
            customer_id: Customer ID for the ticket
            title: Ticket title/subject
            description: Detailed description of the issue
            priority: Ticket priority
            urgency: Ticket urgency

        Returns:
            Ticket creation result
        """
        try:
            response = self._send_request(
                "create_ticket",
                customer_id=customer_id,
                title=title,
                description=description,
                priority=priority,
                urgency=urgency
            )

            return response.get("result", {
                "success": False,
                "error": "No response from service",
                "voice_response": "I'm unable to create a ticket right now."
            })

        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return {
                "success": False,
                "error": str(e),
                "voice_response": "I'm unable to create a ticket right now. Please try again."
            }

    def update_ticket_status(self, ticket_id: int, status: str, comment: str = None) -> Dict:
        """
        Update ticket status via socket service.

        Args:
            ticket_id: Ticket ID to update
            status: New status
            comment: Optional comment

        Returns:
            Update result
        """
        try:
            response = self._send_request(
                "update_ticket_status",
                ticket_id=ticket_id,
                status=status,
                comment=comment
            )

            return response.get("result", {
                "success": False,
                "message": "No response from service"
            })

        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "voice_response": f"I couldn't update ticket {ticket_id}."
            }

    def get_alerts(self, limit: int = 50) -> List[Dict]:
        """
        Get alerts via socket service.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        try:
            response = self._send_request("get_alerts", limit=limit)
            return response.get("alerts", [])

        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

    def search_customer_by_phone(self, phone_number: str) -> Optional[Dict]:
        """
        Search customer by phone via socket service.

        Args:
            phone_number: Phone number to search for

        Returns:
            Customer information if found
        """
        try:
            response = self._send_request(
                "search_customer_by_phone",
                phone_number=phone_number
            )

            return response.get("customer")

        except Exception as e:
            logger.error(f"Failed to search customer by phone: {e}")
            return None

    def get_customer_ticket_summary(self, customer_id: int) -> Dict:
        """
        Get customer ticket summary via socket service.

        Args:
            customer_id: Customer ID

        Returns:
            Voice-ready ticket summary
        """
        try:
            response = self._send_request(
                "get_customer_ticket_summary",
                customer_id=customer_id
            )

            return response.get("summary", {
                "voice_summary": "Unable to retrieve ticket information.",
                "ticket_count": 0
            })

        except Exception as e:
            logger.error(f"Failed to get customer ticket summary: {e}")
            return {
                "voice_summary": "Unable to retrieve ticket information.",
                "ticket_count": 0
            }

    def test_connection(self) -> Dict:
        """
        Test ATERA service connection and health.

        Returns:
            Connection test results
        """
        try:
            response = self._send_request("health_check")

            return {
                "connected": True,
                "service_status": response.get("status", "unknown"),
                "atera_status": response.get("atera_status", "unknown"),
                "last_update": response.get("last_update"),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"ATERA connection test failed: {e}")
            return {
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_voice_response(self, query_type: str = "summary", **kwargs) -> str:
        """
        Get voice-ready response for common queries.

        Args:
            query_type: Type of query (ticket_status, customer_info, etc.)
            **kwargs: Additional parameters for the query

        Returns:
            Voice-ready response string
        """
        try:
            if query_type == "ticket_status":
                customer_id = kwargs.get("customer_id")
                if customer_id:
                    summary = self.get_customer_ticket_summary(customer_id)
                    return summary.get("voice_summary", "No ticket information available.")
                else:
                    return "I need your customer information to check ticket status."

            elif query_type == "customer_info":
                phone = kwargs.get("phone_number")
                if phone:
                    customer = self.search_customer_by_phone(phone)
                    if customer:
                        return f"I found your account for {customer['voice_name']}."
                    else:
                        return "I couldn't locate your account. Could you provide your company name?"
                else:
                    return "I need your phone number or company name to locate your account."

            elif query_type == "create_ticket":
                return "I'd be happy to create a support ticket for you. Could you describe the issue you're experiencing?"

            else:
                return f"Unknown query type: {query_type}"

        except Exception as e:
            logger.error(f"Failed to get voice response for {query_type}: {e}")
            return "I'm experiencing technical difficulties with the support system. Please contact our support team directly."

    def close(self):
        """Close connection (no-op for socket client)."""
        pass

def test_atera_socket_connection(socket_path: str = "/tmp/netovo_atera.sock") -> Dict:
    """
    Test ATERA socket service availability.

    Args:
        socket_path: Path to ATERA service socket

    Returns:
        Test results dictionary
    """
    try:
        client = ATERASocketClient(socket_path)
        result = client.test_connection()
        client.close()
        return result

    except Exception as e:
        return {
            "connected": False,
            "error": f"Socket test failed: {e}",
            "timestamp": datetime.now().isoformat()
        }

# Compatibility aliases for drop-in replacement
SimpleATERAClient = ATERASocketClient
ATERAClient = ATERASocketClient

if __name__ == "__main__":
    # Test the socket client
    print("Testing ATERA socket client...")

    client = ATERASocketClient()

    # Test connection
    connection_test = client.test_connection()
    print(f"Connection test: {connection_test}")

    if connection_test["connected"]:
        # Test voice responses
        print("\nTesting voice responses:")

        ticket_response = client.get_voice_response("ticket_status", customer_id=1)
        print(f"Ticket status: {ticket_response}")

        customer_response = client.get_voice_response("customer_info", phone_number="555-1234")
        print(f"Customer info: {customer_response}")

        create_response = client.get_voice_response("create_ticket")
        print(f"Create ticket: {create_response}")

    client.close()
    print("Socket client test completed.")