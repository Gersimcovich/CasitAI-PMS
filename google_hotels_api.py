"""
Google Hotel Prices API Integration for Casita PMS
Travel Partner API for hotel pricing, availability, and performance reporting

API Documentation: https://developers.google.com/hotels/hotel-prices/api-reference/rest
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class GoogleHotelsAPI:
    """Google Travel Partner API Client for hotel pricing and management"""

    BASE_URL = "https://travelpartner.googleapis.com/v3"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPE = "https://www.googleapis.com/auth/travelpartner"

    def __init__(self, service_account_file: str = None, account_id: str = None):
        self.service_account_file = service_account_file or os.getenv(
            'GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json'
        )
        self.account_id = account_id or os.getenv('GOOGLE_HOTEL_ACCOUNT_ID', '')
        self._access_token = None
        self._token_expiry = None

    def _get_access_token(self) -> str:
        """Get OAuth2 access token using service account credentials"""
        if self._access_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._access_token

        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request

            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=[self.SCOPE]
            )
            credentials.refresh(Request())
            self._access_token = credentials.token
            self._token_expiry = credentials.expiry or (datetime.now() + timedelta(hours=1))
            return self._access_token

        except ImportError:
            raise Exception(
                "google-auth library required. Install with: "
                "pip install google-auth google-auth-httplib2"
            )
        except FileNotFoundError:
            raise Exception(
                f"Service account file not found: {self.service_account_file}. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE in .env"
            )

    def _make_request(self, method: str, endpoint: str, params: Dict = None,
                      data: Dict = None) -> Dict:
        """Make authenticated request to Google Travel Partner API"""
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
            self._access_token = None
            return self._make_request(method, endpoint, params, data)

        if response.status_code >= 400:
            raise Exception(
                f"Google Hotels API error ({response.status_code}): {response.text}"
            )

        return response.json()

    @property
    def _account_path(self) -> str:
        return f"/accounts/{self.account_id}"

    # ============================================
    # HOTELS
    # ============================================

    def set_live_on_google(self, hotel_ids: List[str], live: bool = True) -> Dict:
        """Enable or disable hotels on Google"""
        return self._make_request(
            'POST',
            f'{self._account_path}/hotels:setLiveOnGoogle',
            data={
                'liveOnGoogle': live,
                'hotelIds': hotel_ids
            }
        )

    # ============================================
    # PRICE VIEWS
    # ============================================

    def get_price_view(self, property_id: str) -> Dict:
        """Get price view for a specific property"""
        return self._make_request(
            'GET',
            f'{self._account_path}/priceViews/{property_id}'
        )

    # ============================================
    # ACCOUNT LINKS
    # ============================================

    def list_account_links(self) -> List[Dict]:
        """List all account links"""
        response = self._make_request(
            'GET',
            f'{self._account_path}/accountLinks'
        )
        return response.get('accountLinks', [])

    def get_account_link(self, link_id: str) -> Dict:
        """Get a specific account link"""
        return self._make_request(
            'GET',
            f'{self._account_path}/accountLinks/{link_id}'
        )

    def create_account_link(self, link_data: Dict) -> Dict:
        """Create a new account link"""
        return self._make_request(
            'POST',
            f'{self._account_path}/accountLinks',
            data=link_data
        )

    def update_account_link(self, link_id: str, link_data: Dict) -> Dict:
        """Update an account link"""
        return self._make_request(
            'PATCH',
            f'{self._account_path}/accountLinks/{link_id}',
            data=link_data
        )

    def delete_account_link(self, link_id: str) -> Dict:
        """Delete an account link"""
        return self._make_request(
            'DELETE',
            f'{self._account_path}/accountLinks/{link_id}'
        )

    # ============================================
    # BRANDS
    # ============================================

    def list_brands(self) -> List[Dict]:
        """List all brands"""
        response = self._make_request(
            'GET',
            f'{self._account_path}/brands'
        )
        return response.get('brands', [])

    def get_brand(self, brand_id: str) -> Dict:
        """Get a specific brand"""
        return self._make_request(
            'GET',
            f'{self._account_path}/brands/{brand_id}'
        )

    def create_brand(self, brand_data: Dict) -> Dict:
        """Create a new brand"""
        return self._make_request(
            'POST',
            f'{self._account_path}/brands',
            data=brand_data
        )

    def update_brand(self, brand_id: str, brand_data: Dict) -> Dict:
        """Update a brand"""
        return self._make_request(
            'PATCH',
            f'{self._account_path}/brands/{brand_id}',
            data=brand_data
        )

    # ============================================
    # REPORTS & ANALYTICS
    # ============================================

    def get_participation_report(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        Get participation report showing how properties appear on Google.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        params = {}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date

        return self._make_request(
            'GET',
            f'{self._account_path}/participationReportViews:query',
            params=params
        )

    def get_property_performance_report(self, start_date: str = None,
                                         end_date: str = None) -> Dict:
        """
        Get property performance report with clicks, impressions, and bookings.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        params = {}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date

        return self._make_request(
            'GET',
            f'{self._account_path}/propertyPerformanceReportViews:query',
            params=params
        )

    def get_price_accuracy_views(self) -> Dict:
        """Get price accuracy report to identify pricing discrepancies"""
        return self._make_request(
            'GET',
            f'{self._account_path}/priceAccuracyViews'
        )

    # ============================================
    # RECONCILIATION REPORTS
    # ============================================

    def list_reconciliation_reports(self) -> List[Dict]:
        """List reconciliation reports"""
        response = self._make_request(
            'GET',
            f'{self._account_path}/reconciliationReports'
        )
        return response.get('reconciliationReports', [])

    def create_reconciliation_report(self, report_data: Dict) -> Dict:
        """Create a reconciliation report"""
        return self._make_request(
            'POST',
            f'{self._account_path}/reconciliationReports',
            data=report_data
        )

    # ============================================
    # SYNC FROM CASITA PMS
    # ============================================

    def sync_from_casita_pms(self, pms) -> Dict[str, int]:
        """
        Sync Casita PMS properties to Google Hotels.

        Args:
            pms: CasitaPMS instance

        Returns:
            Dict with counts of synced properties
        """
        stats = {'synced': 0, 'errors': []}

        try:
            properties = pms.get_all_properties()

            for prop in properties:
                try:
                    hotel_id = prop.get('airbnb_listing_id') or str(prop.get('id'))
                    self.set_live_on_google([hotel_id], live=True)
                    stats['synced'] += 1
                except Exception as e:
                    stats['errors'].append(
                        f"Property {prop.get('name')}: {str(e)}"
                    )

        except Exception as e:
            stats['errors'].append(f"PMS Error: {str(e)}")

        return stats


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_google_hotels_client() -> GoogleHotelsAPI:
    """Get Google Hotels API client instance"""
    return GoogleHotelsAPI()


def test_connection() -> bool:
    """Test Google Hotels API connection"""
    try:
        client = GoogleHotelsAPI()
        client._get_access_token()
        return True
    except Exception as e:
        print(f"Google Hotels connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Google Hotels API connection...")

    client = GoogleHotelsAPI()

    try:
        token = client._get_access_token()
        print(f"Authentication successful! Token: {token[:20]}...")

        # Try listing account links
        links = client.list_account_links()
        print(f"Found {len(links)} account links")

        # Try listing brands
        brands = client.list_brands()
        print(f"Found {len(brands)} brands")

    except Exception as e:
        print(f"Error: {e}")
