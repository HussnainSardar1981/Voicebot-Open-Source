#!/home/aiadmin/netovo_voicebot/venv/bin/python3
"""
ATERA API Connection Test
Quick test to validate your ATERA API key and explore available endpoints.
"""

import requests
import json
from datetime import datetime

# ATERA API Configuration
ATERA_API_BASE = "https://app.atera.com/api/v3"

def test_atera_connection(api_key):
    """Test ATERA API connection and explore endpoints."""

    headers = {
        'X-API-KEY': api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    print("🔗 Testing ATERA API Connection...")
    print("=" * 50)

    # Test endpoints to explore
    test_endpoints = [
        {'name': 'Customers', 'url': f'{ATERA_API_BASE}/customers', 'method': 'GET'},
        {'name': 'Tickets', 'url': f'{ATERA_API_BASE}/tickets', 'method': 'GET'},
        {'name': 'Alerts', 'url': f'{ATERA_API_BASE}/alerts', 'method': 'GET'},
        {'name': 'Agents', 'url': f'{ATERA_API_BASE}/agents', 'method': 'GET'},
    ]

    results = {}

    for endpoint in test_endpoints:
        try:
            print(f"\n📡 Testing {endpoint['name']} endpoint...")

            response = requests.get(
                endpoint['url'],
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                results[endpoint['name']] = {
                    'status': 'SUCCESS',
                    'count': len(data.get('items', [])),
                    'sample_data': data
                }
                print(f"✅ {endpoint['name']}: {len(data.get('items', []))} items found")

                # Show sample structure
                if data.get('items') and len(data['items']) > 0:
                    sample = data['items'][0]
                    print(f"   Sample fields: {list(sample.keys())[:5]}...")

            elif response.status_code == 401:
                print(f"❌ {endpoint['name']}: Authentication failed - check API key")
                results[endpoint['name']] = {'status': 'AUTH_FAILED'}

            elif response.status_code == 403:
                print(f"⚠️  {endpoint['name']}: Access forbidden - insufficient permissions")
                results[endpoint['name']] = {'status': 'FORBIDDEN'}

            else:
                print(f"❌ {endpoint['name']}: HTTP {response.status_code}")
                results[endpoint['name']] = {'status': f'HTTP_{response.status_code}'}

        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint['name']}: Connection error - {e}")
            results[endpoint['name']] = {'status': 'CONNECTION_ERROR', 'error': str(e)}

    # Summary
    print("\n" + "=" * 50)
    print("📊 ATERA API TEST SUMMARY")
    print("=" * 50)

    success_count = sum(1 for r in results.values() if r['status'] == 'SUCCESS')
    total_count = len(results)

    print(f"Successful endpoints: {success_count}/{total_count}")

    if success_count > 0:
        print("✅ ATERA API is accessible! Ready to build integration.")

        # Show what we can build
        print("\n🎯 Available for VoiceBot Integration:")
        for name, result in results.items():
            if result['status'] == 'SUCCESS':
                print(f"   ✅ {name}: {result['count']} items available")

        return True, results
    else:
        print("❌ No endpoints accessible. Check API key and permissions.")
        return False, results

def explore_ticket_creation(api_key):
    """Test ticket creation capability."""

    headers = {
        'X-API-KEY': api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    print("\n🎫 Testing Ticket Creation Capability...")

    # First, get customers to use for test ticket
    try:
        customers_response = requests.get(f'{ATERA_API_BASE}/customers', headers=headers)

        if customers_response.status_code == 200:
            customers = customers_response.json().get('items', [])
            if customers:
                customer_id = customers[0]['CustomerID']
                print(f"✅ Found customer for testing: {customers[0].get('CustomerName', 'Unknown')}")

                # Test ticket creation (we won't actually create to avoid spam)
                test_ticket_data = {
                    "TicketTitle": "VoiceBot Integration Test - DO NOT PROCESS",
                    "TicketDescription": "This is a test ticket created during VoiceBot integration testing. Please ignore.",
                    "CustomerID": customer_id,
                    "TicketPriority": "Low",
                    "TicketImpact": "NoImpact",
                    "TicketStatus": "Open",
                    "Source": "API"
                }

                print("✅ Ticket creation payload ready")
                print(f"   Customer ID: {customer_id}")
                print("   Note: Test ticket creation disabled to avoid spam")

                return True, test_ticket_data
            else:
                print("⚠️ No customers found for ticket testing")
                return False, None
        else:
            print(f"❌ Cannot access customers: HTTP {customers_response.status_code}")
            return False, None

    except Exception as e:
        print(f"❌ Error testing ticket creation: {e}")
        return False, None

if __name__ == "__main__":
    print("ATERA API Connection Test")
    print("=" * 50)

    # You'll replace this with your actual API key
    api_key = input("Enter your ATERA API key: ").strip()

    if not api_key:
        print("❌ No API key provided")
        exit(1)

    # Test connection
    success, results = test_atera_connection(api_key)

    if success:
        # Test ticket capabilities
        can_create_tickets, ticket_data = explore_ticket_creation(api_key)

        print("\n🎯 NEXT STEPS:")
        print("1. Update atera_config.py with your API key")
        print("2. Build atera_client.py with full integration")
        print("3. Create voice integration for customer queries")
        print("4. Test with real VoiceBot scenarios")

        # Save results for development
        with open('atera_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print("\n💾 Test results saved to atera_test_results.json")

    else:
        print("\n❌ Fix API connection before proceeding")
        print("Check:")
        print("- API key is correct")
        print("- Account has API access enabled")
        print("- Network connectivity to app.atera.com")