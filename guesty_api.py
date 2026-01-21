"""
Guesty API Integration for Casita PMS
Fetches listings, availability, and pricing from Guesty PMS

API Documentation: https://open-api-docs.guesty.com/
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class GuestyAPI:
    """Guesty API Client for fetching listings and data"""

    # Open API endpoints (requires Open API credentials)
    OPEN_API_BASE_URL = "https://open-api.guesty.com/v1"
    OPEN_API_TOKEN_URL = "https://open-api.guesty.com/oauth2/token"

    # Booking Engine API endpoints (requires Booking Engine credentials)
    BOOKING_API_BASE_URL = "https://booking.guesty.com/api/v1"
    BOOKING_API_TOKEN_URL = "https://booking.guesty.com/oauth2/token"

    def __init__(self, client_id: str = None, client_secret: str = None, use_booking_api: bool = None):
        self.client_id = client_id or os.getenv('GUESTY_CLIENT_ID', '')
        self.client_secret = client_secret or os.getenv('GUESTY_CLIENT_SECRET', '')
        self._access_token = None
        self._token_expiry = None

        # Auto-detect API type or use env var
        if use_booking_api is None:
            use_booking_api = os.getenv('GUESTY_USE_BOOKING_API', 'true').lower() == 'true'

        self.use_booking_api = use_booking_api
        self.BASE_URL = self.BOOKING_API_BASE_URL if use_booking_api else self.OPEN_API_BASE_URL
        self.TOKEN_URL = self.BOOKING_API_TOKEN_URL if use_booking_api else self.OPEN_API_TOKEN_URL

    def _get_access_token(self) -> str:
        """Get OAuth2 access token from Guesty"""
        # Check if we have a valid cached token
        if self._access_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._access_token

        # Set scope based on API type
        scope = 'booking_engine:api' if self.use_booking_api else 'open-api'

        # Request new token
        response = requests.post(
            self.TOKEN_URL,
            data={
                'grant_type': 'client_credentials',
                'scope': scope,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get Guesty access token: {response.text}")

        data = response.json()
        self._access_token = data['access_token']
        # Token expires in 24 hours, refresh 1 hour early
        self._token_expiry = datetime.now() + timedelta(seconds=data.get('expires_in', 86400) - 3600)

        return self._access_token

    def _make_request(self, method: str, endpoint: str, params: Dict = None,
                      data: Dict = None) -> Dict:
        """Make authenticated request to Guesty API"""
        token = self._get_access_token()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data
        )

        if response.status_code == 401:
            # Token expired, clear and retry
            self._access_token = None
            return self._make_request(method, endpoint, params, data)

        if response.status_code >= 400:
            raise Exception(f"Guesty API error ({response.status_code}): {response.text}")

        return response.json()

    # ============================================
    # LISTINGS
    # ============================================

    def search_listings(self, check_in: str = None, check_out: str = None,
                        guests: int = None, location: str = None) -> List[Dict]:
        """
        Search available listings (Booking Engine API).

        Args:
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            guests: Number of guests
            location: Location filter

        Returns:
            List of available listings
        """
        if not self.use_booking_api:
            raise Exception("search_listings requires Booking Engine API credentials")

        params = {}
        if check_in:
            params['checkIn'] = check_in
        if check_out:
            params['checkOut'] = check_out
        if guests:
            params['guests'] = guests
        if location:
            params['location'] = location

        response = self._make_request('GET', '/search', params=params)
        return response.get('results', response) if isinstance(response, dict) else response

    def get_all_listings(self, limit: int = 100, skip: int = 0,
                         active_only: bool = False) -> List[Dict]:
        """Get all listings from Guesty (Open API only)"""
        if self.use_booking_api:
            # For Booking API, use search endpoint without filters
            return self.search_listings()

        params = {
            'limit': limit,
            'skip': skip
        }

        if active_only:
            params['filters'] = json.dumps({'active': {'$eq': True}})

        response = self._make_request('GET', '/listings', params=params)
        return response.get('results', [])

    def get_listing(self, listing_id: str) -> Dict:
        """Get single listing by ID"""
        response = self._make_request('GET', f'/listings/{listing_id}')
        return response

    def get_parent_listings(self, limit: int = 100) -> List[Dict]:
        """Get all parent (MTL) listings"""
        params = {
            'limit': limit,
            'fields': 'title,nickname,address,prices,bedrooms,bathrooms,accommodates,propertyType,type,active',
            'filters': json.dumps({'type': {'$eq': 'MTL'}})
        }

        response = self._make_request('GET', '/listings', params=params)
        return response.get('results', [])

    def get_child_listings(self, parent_id: str) -> List[Dict]:
        """Get all child listings for a parent MTL listing"""
        params = {
            'limit': 100,
            'fields': 'title,nickname,address,prices,bedrooms,bathrooms,accommodates,propertyType,type,active',
            'filters': json.dumps({
                'type': {'$eq': 'MTL_CHILD'},
                'mtl.p': {'$in': [parent_id]}
            })
        }

        response = self._make_request('GET', '/listings', params=params)
        return response.get('results', [])

    def get_single_listings(self, limit: int = 100) -> List[Dict]:
        """Get all single (non-MTL) listings"""
        params = {
            'limit': limit,
            'fields': 'title,nickname,address,prices,bedrooms,bathrooms,accommodates,propertyType,type,active',
            'filters': json.dumps({'type': {'$eq': 'SINGLE'}})
        }

        response = self._make_request('GET', '/listings', params=params)
        return response.get('results', [])

    # ============================================
    # CALENDAR & AVAILABILITY
    # ============================================

    def get_calendar(self, listing_id: str, start_date: str, end_date: str) -> Dict:
        """Get calendar/availability for a listing"""
        response = self._make_request(
            'GET',
            f'/availability-pricing-api/calendar/listings/{listing_id}',
            params={
                'startDate': start_date,
                'endDate': end_date
            }
        )
        return response

    def get_calendar_pricing(self, listing_id: str, days: int = 365) -> List[Dict]:
        """
        Get daily pricing from Guesty calendar.
        This reflects Airbnb Smart Pricing when enabled on the listing.

        Returns list of {date, basePrice, price, minNights, available}
        """
        from datetime import datetime, timedelta

        start = datetime.now().strftime('%Y-%m-%d')
        end = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

        try:
            response = self.get_calendar(listing_id, start, end)

            # Parse calendar data
            pricing_data = []
            data = response.get('data', response)  # Handle different response formats

            if isinstance(data, dict):
                # Calendar data is usually keyed by date
                for date_str, day_data in data.items():
                    if isinstance(day_data, dict):
                        pricing_data.append({
                            'date': date_str,
                            'basePrice': day_data.get('basePrice', day_data.get('price', 0)),
                            'price': day_data.get('price', day_data.get('basePrice', 0)),
                            'minNights': day_data.get('minNights', 1),
                            'available': day_data.get('available', not day_data.get('booked', False)),
                            'status': day_data.get('status', 'available')
                        })
            elif isinstance(data, list):
                for day_data in data:
                    pricing_data.append({
                        'date': day_data.get('date'),
                        'basePrice': day_data.get('basePrice', day_data.get('price', 0)),
                        'price': day_data.get('price', day_data.get('basePrice', 0)),
                        'minNights': day_data.get('minNights', 1),
                        'available': day_data.get('available', True),
                        'status': day_data.get('status', 'available')
                    })

            return sorted(pricing_data, key=lambda x: x['date']) if pricing_data else []

        except Exception as e:
            print(f"Error fetching calendar pricing: {e}")
            return []

    def update_calendar_pricing(self, listing_id: str, start_date: str, end_date: str,
                                 price: float = None, min_nights: int = None,
                                 available: bool = None) -> Dict:
        """Update calendar pricing for a listing (push prices back to Guesty/Airbnb)"""
        data = {
            'startDate': start_date,
            'endDate': end_date
        }
        if price is not None:
            data['price'] = price
        if min_nights is not None:
            data['minNights'] = min_nights
        if available is not None:
            data['available'] = available

        return self._make_request(
            'PUT',
            f'/availability-pricing-api/calendar/listings/{listing_id}',
            data=data
        )

    def get_availability(self, listing_ids: List[str], check_in: str,
                         check_out: str, min_occupancy: int = 1) -> List[Dict]:
        """Check availability for listings"""
        params = {
            'ids': ','.join(listing_ids),
            'available': json.dumps({
                'checkIn': check_in,
                'checkOut': check_out,
                'minOccupancy': min_occupancy
            })
        }

        response = self._make_request('GET', '/listings', params=params)
        return response.get('results', [])

    # ============================================
    # MESSAGING & SAVED REPLIES (for AI Bot)
    # ============================================

    def get_saved_replies(self, limit: int = 100) -> List[Dict]:
        """Get all saved replies (canned responses) from Guesty"""
        response = self._make_request('GET', '/saved-replies', params={'limit': limit})
        return response.get('results', response) if isinstance(response, dict) else response

    def get_saved_reply(self, reply_id: str) -> Dict:
        """Get a specific saved reply by ID"""
        return self._make_request('GET', f'/saved-replies/{reply_id}')

    def get_saved_replies_by_listing(self, listing_id: str) -> List[Dict]:
        """Get saved replies assigned to a specific listing"""
        response = self._make_request('GET', f'/saved-replies/listing/{listing_id}')
        return response.get('results', response) if isinstance(response, dict) else response

    def get_conversations(self, limit: int = 50, listing_id: str = None) -> List[Dict]:
        """Get guest conversations from Guesty inbox"""
        params = {'limit': limit}
        if listing_id:
            params['listingId'] = listing_id
        response = self._make_request('GET', '/communication/conversations', params=params)
        return response.get('results', response) if isinstance(response, dict) else response

    def get_conversation(self, conversation_id: str) -> Dict:
        """Get a specific conversation by ID"""
        return self._make_request('GET', f'/communication/conversations/{conversation_id}')

    def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get messages (posts) from a conversation"""
        response = self._make_request(
            'GET',
            f'/communication/conversations/{conversation_id}/posts',
            params={'limit': limit}
        )
        return response.get('results', response) if isinstance(response, dict) else response

    def send_message(self, conversation_id: str, message: str, module: str = 'airbnb2') -> Dict:
        """
        Send a message to a guest conversation.

        Args:
            conversation_id: The conversation ID
            message: The message text to send
            module: Channel module type ('airbnb2', 'email', etc.)
        """
        return self._make_request(
            'POST',
            f'/communication/conversations/{conversation_id}/send-message',
            data={
                'body': message,
                'module': module
            }
        )

    def create_draft_message(self, conversation_id: str, message: str) -> Dict:
        """Create a draft message without sending (for agent review)"""
        return self._make_request(
            'POST',
            f'/communication/conversations/{conversation_id}/posts',
            data={'body': message}
        )

    # ============================================
    # RESERVATIONS
    # ============================================

    def get_reservations(self, listing_id: str = None, start_date: str = None,
                         end_date: str = None, limit: int = 100) -> List[Dict]:
        """Get reservations"""
        params = {
            'limit': limit,
            'fields': 'listingId,checkIn,checkOut,status,money,guest,source'
        }

        filters = {}
        if listing_id:
            filters['listingId'] = {'$eq': listing_id}
        if start_date:
            filters['checkIn'] = {'$gte': start_date}
        if end_date:
            filters['checkOut'] = {'$lte': end_date}

        if filters:
            params['filters'] = json.dumps(filters)

        response = self._make_request('GET', '/reservations', params=params)
        return response.get('results', [])

    # ============================================
    # SYNC TO CASITA PMS
    # ============================================

    def sync_to_casita_pms(self, pms) -> Dict[str, int]:
        """
        Sync all Guesty listings to Casita PMS database

        Args:
            pms: CasitaPMS instance

        Returns:
            Dict with counts of synced properties and units
        """
        stats = {'properties': 0, 'units': 0, 'errors': []}

        try:
            # Get all listings
            all_listings = self.get_all_listings(limit=200)

            # Separate by type
            parents = [l for l in all_listings if l.get('type') == 'MTL']
            singles = [l for l in all_listings if l.get('type') == 'SINGLE']
            children = [l for l in all_listings if l.get('type') == 'MTL_CHILD']

            # Process parent listings (MTL)
            for listing in parents:
                try:
                    # Extract data
                    address = listing.get('address', {})
                    prices = listing.get('prices', {})

                    prop_id = pms.create_property(
                        name=listing.get('title', 'Unnamed Property'),
                        nickname=listing.get('nickname'),
                        property_type='MTL',
                        city=address.get('city'),
                        state=address.get('state'),
                        address=address.get('full'),
                        base_price=prices.get('basePrice', 0),
                        min_price=prices.get('minPrice', 0),
                        max_price=prices.get('maxPrice', 9999),
                        bedrooms=listing.get('bedrooms'),
                        bathrooms=listing.get('bathrooms'),
                        max_guests=listing.get('accommodates'),
                        airbnb_listing_id=listing.get('_id')
                    )
                    stats['properties'] += 1

                    # Get and create child units
                    listing_children = [c for c in children if c.get('mtl', {}).get('p') == listing.get('_id')]
                    for child in listing_children:
                        try:
                            child_prices = child.get('prices', {})
                            pms.create_unit(
                                property_id=prop_id,
                                unit_name=child.get('title', 'Unnamed Unit'),
                                unit_type=child.get('propertyType', 'Standard'),
                                airbnb_listing_id=child.get('_id'),
                                bedrooms=child.get('bedrooms'),
                                bathrooms=child.get('bathrooms'),
                                max_guests=child.get('accommodates'),
                                custom_base_price=child_prices.get('basePrice'),
                                custom_min_price=child_prices.get('minPrice'),
                                custom_max_price=child_prices.get('maxPrice')
                            )
                            stats['units'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Unit {child.get('title')}: {str(e)}")

                except Exception as e:
                    stats['errors'].append(f"Property {listing.get('title')}: {str(e)}")

            # Process single listings (create as property + 1 unit)
            for listing in singles:
                try:
                    address = listing.get('address', {})
                    prices = listing.get('prices', {})

                    prop_id = pms.create_property(
                        name=listing.get('title', 'Unnamed Property'),
                        nickname=listing.get('nickname'),
                        property_type='SINGLE',
                        city=address.get('city'),
                        state=address.get('state'),
                        address=address.get('full'),
                        base_price=prices.get('basePrice', 0),
                        min_price=prices.get('minPrice', 0),
                        max_price=prices.get('maxPrice', 9999),
                        bedrooms=listing.get('bedrooms'),
                        bathrooms=listing.get('bathrooms'),
                        max_guests=listing.get('accommodates'),
                        airbnb_listing_id=listing.get('_id')
                    )
                    stats['properties'] += 1

                    # Create single unit for the property
                    pms.create_unit(
                        property_id=prop_id,
                        unit_name=listing.get('title', 'Main Unit'),
                        unit_type=listing.get('propertyType', 'Single'),
                        airbnb_listing_id=listing.get('_id'),
                        bedrooms=listing.get('bedrooms'),
                        bathrooms=listing.get('bathrooms'),
                        max_guests=listing.get('accommodates')
                    )
                    stats['units'] += 1

                except Exception as e:
                    stats['errors'].append(f"Single {listing.get('title')}: {str(e)}")

        except Exception as e:
            stats['errors'].append(f"API Error: {str(e)}")

        return stats


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_guesty_client() -> GuestyAPI:
    """Get Guesty API client instance"""
    return GuestyAPI()


def test_connection() -> bool:
    """Test Guesty API connection"""
    try:
        client = GuestyAPI()
        listings = client.get_all_listings(limit=1)
        return True
    except Exception as e:
        print(f"Guesty connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test the API connection
    print("Testing Guesty API connection...")

    client = GuestyAPI()

    try:
        listings = client.get_all_listings(limit=10)
        print(f"\nFound {len(listings)} listings:")

        for listing in listings:
            print(f"  - {listing.get('title')} ({listing.get('type', 'SINGLE')})")
            print(f"    ID: {listing.get('_id')}")
            print(f"    Address: {listing.get('address', {}).get('full', 'N/A')}")
            prices = listing.get('prices', {})
            print(f"    Base Price: ${prices.get('basePrice', 0)}")
            print()

    except Exception as e:
        print(f"Error: {e}")
