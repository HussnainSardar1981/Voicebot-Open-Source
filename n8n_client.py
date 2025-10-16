#!/usr/bin/env python3
"""
N8N Client for NETOVO VoiceBot Integration
Simple HTTP client to send ticket creation requests to n8n workflows
"""

import requests
import logging
import os
import json
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class N8NClient:
    """
    Lightweight n8n webhook client for VoiceBot integration
    Sends ticket creation requests to n8n Atera workflow
    """

    def __init__(self, base_url: str = None, timeout: int = 10):
        self.base_url = base_url or "http://localhost:5678"
        self.timeout = timeout
        self.session = requests.Session()

        # Set headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'NETOVO-VoiceBot/1.0'
        })

        logger.info(f"N8N client initialized: {self.base_url}")

    def create_ticket(self, call_data: Dict) -> Dict:
        """
        Send ticket creation request to n8n Atera workflow

        Args:
            call_data: {
                "caller_id": str,     # Phone number
                "transcript": str,    # Call transcript
                "customer_name": str  # Optional customer name
            }

        Returns:
            {
                "status": "success",
                "ticket_id": str,
                "ticket_number": str,
                "message": str
            }

        Raises:
            N8NError: If n8n request fails
        """
        try:
            # Validate required fields
            if not call_data.get('caller_id'):
                raise ValueError("caller_id is required")
            if not call_data.get('transcript'):
                raise ValueError("transcript is required")

            # Prepare request payload
            payload = {
                "caller_id": str(call_data['caller_id']).strip(),
                "transcript": str(call_data['transcript']).strip(),
                "customer_name": call_data.get('customer_name', 'Unknown Customer')
            }

            logger.info(f"Sending ticket request to n8n for caller: {payload['caller_id']}")

            # Send webhook request
            response = self.session.post(
                f"{self.base_url}/webhook/create-ticket",
                json=payload,
                timeout=self.timeout
            )

            # Check HTTP status
            response.raise_for_status()

            # Parse response
            result = response.json()

            if result.get('status') == 'success':
                logger.info(f"Ticket created successfully: {result.get('ticket_number')}")
                return result
            else:
                error_msg = result.get('message', 'Unknown error from n8n')
                logger.error(f"N8N workflow failed: {error_msg}")
                raise N8NError(f"Workflow failed: {error_msg}")

        except requests.exceptions.Timeout:
            logger.error("N8N request timeout - service may be slow")
            raise N8NError("Request timeout - n8n service unavailable")

        except requests.exceptions.ConnectionError:
            logger.error("N8N connection failed - service may be down")
            raise N8NError("Connection failed - n8n service down")

        except requests.exceptions.HTTPError as e:
            logger.error(f"N8N HTTP error: {e.response.status_code}")
            raise N8NError(f"HTTP {e.response.status_code}: {e.response.text}")

        except (ValueError, KeyError) as e:
            logger.error(f"Invalid request data: {e}")
            raise N8NError(f"Invalid data: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in n8n request: {e}")
            raise N8NError(f"Unexpected error: {e}")

    def health_check(self) -> bool:
        """
        Check if n8n service is healthy and responsive

        Returns:
            bool: True if n8n is healthy, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/healthz",
                timeout=5
            )

            if response.status_code == 200:
                health_data = response.json()
                is_healthy = health_data.get('status') == 'ok'
                logger.info(f"N8N health check: {'healthy' if is_healthy else 'unhealthy'}")
                return is_healthy
            else:
                logger.warning(f"N8N health check failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"N8N health check error: {e}")
            return False

    def test_workflow(self) -> Dict:
        """
        Test the Atera workflow with sample data

        Returns:
            Dict: Test result
        """
        test_data = {
            "caller_id": "+15551234567",
            "transcript": "Test call from voicebot integration - please ignore",
            "customer_name": "Test Customer"
        }

        try:
            result = self.create_ticket(test_data)
            logger.info("Workflow test successful")
            return {"test_status": "success", "result": result}
        except N8NError as e:
            logger.error(f"Workflow test failed: {e}")
            return {"test_status": "failed", "error": str(e)}


class N8NError(Exception):
    """Raised when N8N operations fail"""
    pass


# Simple usage example
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create client
    client = N8NClient()

    # Test health check
    if client.health_check():
        print("N8N service is healthy")

        # Test workflow (optional)
        test_result = client.test_workflow()
        print(f"Workflow test: {test_result['test_status']}")

        if test_result['test_status'] == 'success':
            print(f"Test ticket created: {test_result['result']['ticket_number']}")
    else:
        print("N8N service is not healthy")
