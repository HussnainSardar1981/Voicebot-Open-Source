#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA Service Extension for NETOVO Model Warmup Service

Purpose: Extends the existing model_warmup_service.py with ATERA MSP capabilities
         following the same architecture pattern for consistent integration.

This module provides:
- ATERA client initialization and management
- Socket request handlers for ATERA operations
- Health monitoring and status reporting
- Seamless integration with existing service architecture

Usage: Add this to your model_warmup_service.py or import as extension
"""

import json
import socket
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Any

# Import ATERA components
from atera_client import ATERAClient
from atera_config import ATERA_CONFIG, ATERA_SOCKET_CONFIG

logger = logging.getLogger(__name__)

class ATERAServiceExtension:
    """
    ATERA service extension for model warmup service integration.

    This class provides ATERA MSP capabilities that integrate
    seamlessly with the existing socket-based service architecture.
    """

    def __init__(self):
        """Initialize ATERA service extension."""
        self.atera_client = None
        self.last_health_check = None
        self.customer_cache = {}
        self.cache_timeout = 300  # 5 minutes
        self.is_healthy = False

        logger.info("ATERAServiceExtension initialized")

    def initialize_atera_client(self) -> bool:
        """
        Initialize ATERA client with error handling.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing ATERA client...")

            # Create client instance
            self.atera_client = ATERAClient(ATERA_CONFIG)

            # Test connection
            connection_test = self.atera_client.test_connection()
            if connection_test["connected"]:
                self.is_healthy = True
                self.last_health_check = datetime.now()

                logger.info(f"ATERA client initialized successfully")
                logger.info(f"Customer access: {connection_test.get('customer_count', 0)} customers available")

                # Warm up customer cache
                self._warm_customer_cache()

                return True
            else:
                logger.error(f"ATERA connection test failed: {connection_test.get('error', 'unknown')}")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize ATERA client: {e}")
            self.is_healthy = False
            return False

    def _warm_customer_cache(self):
        """Pre-load customer cache for faster lookups."""
        try:
            customers = self.atera_client.get_customers(limit=100)
            for customer in customers:
                self.customer_cache[customer['id']] = {
                    'data': customer,
                    'timestamp': datetime.now()
                }
            logger.info(f"Warmed customer cache with {len(customers)} customers")
        except Exception as e:
            logger.warning(f"Failed to warm customer cache: {e}")

    def handle_atera_request(self, request: Dict) -> Dict:
        """
        Handle ATERA-related socket requests.

        Args:
            request: Request dictionary with action and parameters

        Returns:
            Response dictionary
        """
        try:
            action = request.get("action")
            timestamp = request.get("timestamp", datetime.now().isoformat())

            logger.debug(f"Handling ATERA request: {action}")

            # Check if ATERA client is available
            if not self.atera_client or not self.is_healthy:
                return {
                    "status": "error",
                    "message": "ATERA service is not available",
                    "timestamp": timestamp
                }

            # Route request to appropriate handler
            if action == "get_customers":
                return self._handle_get_customers(request)
            elif action == "get_tickets":
                return self._handle_get_tickets(request)
            elif action == "create_ticket":
                return self._handle_create_ticket(request)
            elif action == "update_ticket_status":
                return self._handle_update_ticket_status(request)
            elif action == "get_alerts":
                return self._handle_get_alerts(request)
            elif action == "search_customer_by_phone":
                return self._handle_search_customer_by_phone(request)
            elif action == "get_customer_ticket_summary":
                return self._handle_get_customer_ticket_summary(request)
            elif action == "health_check":
                return self._handle_health_check(request)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown ATERA action: {action}",
                    "timestamp": timestamp
                }

        except Exception as e:
            logger.error(f"Error handling ATERA request: {e}")
            return {
                "status": "error",
                "message": f"Request processing error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _handle_get_customers(self, request: Dict) -> Dict:
        """Handle get_customers request."""
        try:
            search_term = request.get("search_term")
            limit = request.get("limit", 50)

            customers = self.atera_client.get_customers(
                search_term=search_term,
                limit=limit
            )

            return {
                "status": "success",
                "customers": customers,
                "count": len(customers),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting customers: {e}")
            return {
                "status": "error",
                "message": str(e),
                "customers": [],
                "timestamp": datetime.now().isoformat()
            }

    def _handle_get_tickets(self, request: Dict) -> Dict:
        """Handle get_tickets request."""
        try:
            customer_id = request.get("customer_id")
            status = request.get("status")
            limit = request.get("limit", 50)

            tickets = self.atera_client.get_tickets(
                customer_id=customer_id,
                status=status,
                limit=limit
            )

            return {
                "status": "success",
                "tickets": tickets,
                "count": len(tickets),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting tickets: {e}")
            return {
                "status": "error",
                "message": str(e),
                "tickets": [],
                "timestamp": datetime.now().isoformat()
            }

    def _handle_create_ticket(self, request: Dict) -> Dict:
        """Handle create_ticket request."""
        try:
            customer_id = request.get("customer_id")
            title = request.get("title")
            description = request.get("description")
            priority = request.get("priority", "Medium")
            urgency = request.get("urgency", "Medium")

            if not all([customer_id, title, description]):
                return {
                    "status": "error",
                    "message": "Missing required fields: customer_id, title, description",
                    "timestamp": datetime.now().isoformat()
                }

            result = self.atera_client.create_ticket(
                customer_id=customer_id,
                title=title,
                description=description,
                priority=priority,
                urgency=urgency
            )

            return {
                "status": "success" if result['success'] else "error",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return {
                "status": "error",
                "message": str(e),
                "result": {
                    "success": False,
                    "error": str(e),
                    "voice_response": "I'm unable to create a ticket right now."
                },
                "timestamp": datetime.now().isoformat()
            }

    def _handle_update_ticket_status(self, request: Dict) -> Dict:
        """Handle update_ticket_status request."""
        try:
            ticket_id = request.get("ticket_id")
            status = request.get("status")
            comment = request.get("comment")

            if not all([ticket_id, status]):
                return {
                    "status": "error",
                    "message": "Missing required fields: ticket_id, status",
                    "timestamp": datetime.now().isoformat()
                }

            result = self.atera_client.update_ticket_status(
                ticket_id=ticket_id,
                status=status,
                comment=comment
            )

            return {
                "status": "success" if result['success'] else "error",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")
            return {
                "status": "error",
                "message": str(e),
                "result": {
                    "success": False,
                    "error": str(e)
                },
                "timestamp": datetime.now().isoformat()
            }

    def _handle_get_alerts(self, request: Dict) -> Dict:
        """Handle get_alerts request."""
        try:
            limit = request.get("limit", 50)

            alerts = self.atera_client.get_alerts(limit=limit)

            return {
                "status": "success",
                "alerts": alerts,
                "count": len(alerts),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return {
                "status": "error",
                "message": str(e),
                "alerts": [],
                "timestamp": datetime.now().isoformat()
            }

    def _handle_search_customer_by_phone(self, request: Dict) -> Dict:
        """Handle search_customer_by_phone request."""
        try:
            phone_number = request.get("phone_number")

            if not phone_number:
                return {
                    "status": "error",
                    "message": "Phone number is required",
                    "timestamp": datetime.now().isoformat()
                }

            customer = self.atera_client.search_customer_by_phone(phone_number)

            return {
                "status": "success",
                "customer": customer,
                "found": customer is not None,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error searching customer by phone: {e}")
            return {
                "status": "error",
                "message": str(e),
                "customer": None,
                "timestamp": datetime.now().isoformat()
            }

    def _handle_get_customer_ticket_summary(self, request: Dict) -> Dict:
        """Handle get_customer_ticket_summary request with caching."""
        try:
            customer_id = request.get("customer_id")

            if not customer_id:
                return {
                    "status": "error",
                    "message": "Customer ID is required",
                    "timestamp": datetime.now().isoformat()
                }

            # Check cache first
            cache_key = f"ticket_summary_{customer_id}"
            if self._is_cache_valid(cache_key):
                logger.debug("Returning cached ticket summary")
                return {
                    "status": "success",
                    "summary": self.customer_cache[cache_key]["data"],
                    "cached": True,
                    "timestamp": datetime.now().isoformat()
                }

            # Get fresh data
            summary = self.atera_client.get_customer_ticket_summary(customer_id)

            # Cache the result
            self.customer_cache[cache_key] = {
                "data": summary,
                "timestamp": datetime.now()
            }

            return {
                "status": "success",
                "summary": summary,
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting customer ticket summary: {e}")
            return {
                "status": "error",
                "message": str(e),
                "summary": {
                    "voice_summary": "Unable to retrieve ticket information.",
                    "ticket_count": 0
                },
                "timestamp": datetime.now().isoformat()
            }

    def _handle_health_check(self, request: Dict) -> Dict:
        """Handle health_check request."""
        try:
            # Perform health check
            connection_test = self.atera_client.test_connection()
            self.is_healthy = connection_test["connected"]
            self.last_health_check = datetime.now()

            return {
                "status": "success",
                "atera_status": "healthy" if self.is_healthy else "unhealthy",
                "connection_test": connection_test,
                "last_update": self.last_health_check.isoformat(),
                "cache_entries": len(self.customer_cache),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error during health check: {e}")
            self.is_healthy = False
            return {
                "status": "error",
                "message": str(e),
                "atera_status": "unhealthy",
                "timestamp": datetime.now().isoformat()
            }

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.customer_cache:
            return False

        cache_age = datetime.now() - self.customer_cache[cache_key]["timestamp"]
        return cache_age.total_seconds() < self.cache_timeout

    def cleanup(self):
        """Cleanup ATERA resources."""
        if self.atera_client:
            try:
                # ATERA client doesn't need explicit cleanup, but we can log
                logger.info("ATERA client cleanup completed")
            except Exception as e:
                logger.error(f"Error during ATERA cleanup: {e}")

        self.customer_cache.clear()

# =============================================================================
# INTEGRATION CODE FOR model_warmup_service.py
# =============================================================================

def add_atera_to_model_service():
    """
    Integration code to add to your existing model_warmup_service.py

    Add this code to your ModelWarmupService class:

    1. In __init__ method, add:
       self.atera_service = ATERAServiceExtension()

    2. In load_models method, add:
       if self.atera_service.initialize_atera_client():
           logger.info("ATERA MSP service loaded successfully")
       else:
           logger.warning("ATERA MSP service failed to load")

    3. In _handle_client_request method, add this case:
       elif action.startswith("atera_"):
           # Handle ATERA requests
           atera_action = action.replace("atera_", "")
           request_data["action"] = atera_action
           return self.atera_service.handle_atera_request(request_data)

    4. In signal_handler method, add:
       if hasattr(self, 'atera_service'):
           self.atera_service.cleanup()

    5. Add health check in keep_alive method:
       if hasattr(self, 'atera_service') and self.atera_service.is_healthy:
           logger.debug("ATERA service health check passed")
    """
    pass

# =============================================================================
# SOCKET PROTOCOL EXTENSION
# =============================================================================

ATERA_SOCKET_PROTOCOL = {
    "get_customers": {
        "description": "Get customer list with optional search",
        "parameters": {
            "search_term": "Optional search term for customer name",
            "limit": "Maximum number of customers to return"
        },
        "example": {
            "action": "atera_get_customers",
            "search_term": "Acme Corp",
            "limit": 10
        }
    },
    "get_tickets": {
        "description": "Get tickets with optional filtering",
        "parameters": {
            "customer_id": "Filter by specific customer",
            "status": "Filter by ticket status",
            "limit": "Maximum number of tickets to return"
        },
        "example": {
            "action": "atera_get_tickets",
            "customer_id": 123,
            "status": "Open",
            "limit": 20
        }
    },
    "create_ticket": {
        "description": "Create new support ticket",
        "parameters": {
            "customer_id": "Customer ID for the ticket",
            "title": "Ticket title/subject",
            "description": "Detailed description of the issue",
            "priority": "Ticket priority (Low, Medium, High, Critical)",
            "urgency": "Ticket urgency (Low, Medium, High, Critical)"
        },
        "example": {
            "action": "atera_create_ticket",
            "customer_id": 123,
            "title": "Email server down",
            "description": "Unable to send or receive emails",
            "priority": "High",
            "urgency": "High"
        }
    },
    "search_customer_by_phone": {
        "description": "Search for customer by phone number",
        "parameters": {
            "phone_number": "Phone number to search for"
        },
        "example": {
            "action": "atera_search_customer_by_phone",
            "phone_number": "555-123-4567"
        }
    },
    "get_customer_ticket_summary": {
        "description": "Get voice-ready ticket summary for customer",
        "parameters": {
            "customer_id": "Customer ID"
        },
        "example": {
            "action": "atera_get_customer_ticket_summary",
            "customer_id": 123
        }
    },
    "health_check": {
        "description": "Check ATERA service health",
        "parameters": {},
        "example": {
            "action": "atera_health_check"
        }
    }
}

if __name__ == "__main__":
    # Test the service extension
    print("Testing ATERA Service Extension...")

    extension = ATERAServiceExtension()

    # Test initialization
    if extension.initialize_atera_client():
        print("✓ ATERA client initialized successfully")

        # Test request handling
        test_requests = [
            {"action": "health_check"},
            {"action": "get_customers", "limit": 3},
            {"action": "get_tickets", "limit": 5}
        ]

        for request in test_requests:
            print(f"\nTesting request: {request['action']}")
            response = extension.handle_atera_request(request)
            print(f"Response status: {response.get('status', 'unknown')}")

        extension.cleanup()
        print("✓ Service extension test completed")
    else:
        print("✗ Failed to initialize ATERA client")
        print("Note: This is expected if ATERA API key is not configured")