"""
Hotel Intelligence Module
Real hotel pricing and availability data for competitor analysis.

Supports multiple data providers:
- Google Hotels (Travel Partner API) - primary
- Amadeus - legacy fallback
- Simulated data - demo/development

Features:
- Hotel discovery by location (geocode)
- Real-time hotel offers/pricing
- 60-day pricing forecast
- Competitor set tracking
"""

import datetime
import pandas as pd
from typing import List, Dict, Optional


# ============================================
# PROVIDER-AGNOSTIC INTERFACE
# ============================================

def get_monitored_leads(provider, latitude: float = 25.7826, longitude: float = -80.1340,
                        radius: int = 5, radius_unit: str = 'KM') -> List[Dict]:
    """
    Finds all hotels in a given area.

    Args:
        provider: API client (GoogleHotelsAPI or Amadeus client)
        latitude: Center point latitude (default: South Beach)
        longitude: Center point longitude (default: South Beach)
        radius: Search radius
        radius_unit: 'KM' or 'MILE'

    Returns:
        List of hotel objects with name and hotelId
    """
    provider_name = type(provider).__name__

    if provider_name == 'GoogleHotelsAPI':
        return _google_get_monitored_leads(provider, latitude, longitude, radius)
    else:
        return _amadeus_get_monitored_leads(provider, latitude, longitude, radius, radius_unit)


def get_hotel_offers(provider, hotel_ids: List[str], check_in: str = "",
                     check_out: str = "", adults: int = 2) -> List[Dict]:
    """
    Get real hotel offers/pricing.

    Args:
        provider: API client (GoogleHotelsAPI or Amadeus client)
        hotel_ids: List of hotel IDs to query
        check_in: Check-in date (YYYY-MM-DD), defaults to today
        check_out: Check-out date (YYYY-MM-DD), defaults to tomorrow
        adults: Number of adults

    Returns:
        List of hotel offers with pricing
    """
    if not check_in:
        check_in = datetime.date.today().isoformat()
    if not check_out:
        check_out = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    provider_name = type(provider).__name__

    if provider_name == 'GoogleHotelsAPI':
        return _google_get_hotel_offers(provider, hotel_ids, check_in, check_out)
    else:
        return _amadeus_get_hotel_offers(provider, hotel_ids, check_in, check_out, adults)


def get_hotel_pricing_range(provider, hotel_id: str, days: int = 60,
                            adults: int = 2) -> pd.DataFrame:
    """
    Get pricing data for a hotel over a date range.

    Args:
        provider: API client
        hotel_id: Single hotel ID
        days: Number of days to query (default 60)
        adults: Number of adults

    Returns:
        DataFrame with date, room types, rates, availability
    """
    provider_name = type(provider).__name__

    if provider_name == 'GoogleHotelsAPI':
        return _google_get_pricing_range(provider, hotel_id, days)
    else:
        return _amadeus_get_pricing_range(provider, hotel_id, days, adults)


def get_60_day_insight(provider, hotel_id: str) -> pd.DataFrame:
    """
    60-Day pricing insight for a specific hotel.
    Uses real API when available, falls back to simulation.

    Args:
        provider: API client
        hotel_id: Hotel ID to query

    Returns:
        DataFrame with pricing data
    """
    provider_name = type(provider).__name__

    if provider_name == 'GoogleHotelsAPI':
        return _google_60_day_insight(provider, hotel_id)
    else:
        return _amadeus_60_day_insight(provider, hotel_id)


def get_comp_set_summary(provider, hotel_ids: List[str], check_in: str = "") -> pd.DataFrame:
    """
    Get competitive set pricing summary for a specific date.

    Args:
        provider: API client
        hotel_ids: List of competitor hotel IDs
        check_in: Date to check (defaults to today)

    Returns:
        DataFrame with hotel pricing comparison
    """
    if not check_in:
        check_in = datetime.date.today().isoformat()

    check_out = (datetime.date.fromisoformat(check_in) + datetime.timedelta(days=1)).isoformat()

    offers = get_hotel_offers(provider, hotel_ids, check_in, check_out)

    if not offers:
        return pd.DataFrame()

    summary = []
    for hotel in offers:
        hotel_name = hotel.get('hotel', {}).get('name', 'Unknown')
        hotel_id = hotel.get('hotel', {}).get('hotelId', '')

        prices = []
        for offer in hotel.get('offers', []):
            price = float(offer.get('price', {}).get('total', 0))
            if price > 0:
                prices.append(price)

        if prices:
            summary.append({
                "Hotel": hotel_name,
                "Hotel ID": hotel_id,
                "Lowest Rate": min(prices),
                "Highest Rate": max(prices),
                "Avg Rate": sum(prices) / len(prices),
                "Room Types Available": len(prices)
            })

    return pd.DataFrame(summary)


def search_hotels_by_city(provider, city_code: str, radius: int = 20) -> List[Dict]:
    """
    Search hotels by IATA city code (Amadeus) or location (Google).

    Args:
        provider: API client
        city_code: IATA city code (e.g., 'MIA' for Miami)
        radius: Search radius in KM

    Returns:
        List of hotels
    """
    provider_name = type(provider).__name__

    if provider_name == 'GoogleHotelsAPI':
        return _google_get_monitored_leads(provider)
    else:
        return _amadeus_search_by_city(provider, city_code, radius)


# ============================================
# GOOGLE HOTELS IMPLEMENTATION
# ============================================

def _google_get_monitored_leads(provider, latitude: float = 25.7826,
                                 longitude: float = -80.1340,
                                 radius: int = 5) -> List[Dict]:
    """Get hotels using Google Travel Partner API"""
    try:
        # Get account links/brands which represent connected properties
        brands = provider.list_brands()
        hotels = []

        for brand in brands:
            brand_name = brand.get('displayName', brand.get('name', 'Unknown'))
            brand_id = brand.get('name', '').split('/')[-1] if brand.get('name') else ''
            hotels.append({
                'hotel': {
                    'name': brand_name,
                    'hotelId': brand_id
                }
            })

        if not hotels:
            # Try getting price views as alternative
            try:
                report = provider.get_participation_report()
                results = report.get('results', [])
                for r in results:
                    prop = r.get('property', {})
                    hotels.append({
                        'hotel': {
                            'name': prop.get('name', 'Property'),
                            'hotelId': prop.get('propertyId', '')
                        }
                    })
            except Exception:
                pass

        return hotels

    except Exception as e:
        print(f"Google Hotels API Error: {e}")
        return []


def _google_get_hotel_offers(provider, hotel_ids: List[str],
                              check_in: str, check_out: str) -> List[Dict]:
    """Get hotel price views from Google"""
    offers = []

    for hotel_id in hotel_ids:
        try:
            price_view = provider.get_price_view(hotel_id)

            offers.append({
                'hotel': {
                    'name': price_view.get('propertyName', hotel_id),
                    'hotelId': hotel_id
                },
                'offers': [{
                    'price': {
                        'total': price_view.get('price', {}).get('amount', 0),
                        'currency': price_view.get('price', {}).get('currencyCode', 'USD')
                    },
                    'room': {
                        'typeEstimated': {
                            'category': price_view.get('roomType', 'Standard')
                        }
                    },
                    'available': True
                }]
            })

        except Exception as e:
            print(f"Error fetching price view for {hotel_id}: {e}")

    return offers


def _google_get_pricing_range(provider, hotel_id: str, days: int = 60) -> pd.DataFrame:
    """Get pricing range from Google Hotels"""
    try:
        # Google Travel Partner can provide price views per property
        price_view = provider.get_price_view(hotel_id)

        if price_view:
            # Build DataFrame from available data
            data = []
            today = datetime.date.today()

            rates = price_view.get('rates', [price_view])
            for rate in rates if isinstance(rates, list) else [rates]:
                price = float(rate.get('price', {}).get('amount', 0))
                room_type = rate.get('roomType', 'Standard')

                if price > 0:
                    data.append({
                        "Date": today,
                        "Hotel": price_view.get('propertyName', hotel_id),
                        "Room Type": room_type,
                        "Rate": price,
                        "Rate_Display": f"${price:.0f}",
                        "Currency": rate.get('price', {}).get('currencyCode', 'USD'),
                        "Available": "✅ Available",
                        "Cancellation": "See property"
                    })

            if data:
                return pd.DataFrame(data)

    except Exception as e:
        print(f"Error fetching Google pricing range: {e}")

    return pd.DataFrame()


def _google_60_day_insight(provider, hotel_id: str) -> pd.DataFrame:
    """60-day insight using Google Hotels API with simulation fallback"""
    try:
        df = _google_get_pricing_range(provider, hotel_id)
        if not df.empty:
            return df
    except Exception as e:
        print(f"Using simulated data (Google API: {e})")

    # Performance reports as alternative source
    try:
        report = provider.get_property_performance_report()
        results = report.get('results', [])
        if results:
            data = []
            for r in results:
                data.append({
                    "Date": r.get('date', datetime.date.today()),
                    "Clicks": r.get('clicks', 0),
                    "Impressions": r.get('impressions', 0),
                    "Bookings": r.get('bookings', 0)
                })
            if data:
                return pd.DataFrame(data)
    except Exception:
        pass

    # Fallback to simulation
    return _generate_simulated_data(hotel_id, days=60)


# ============================================
# AMADEUS IMPLEMENTATION (LEGACY)
# ============================================

def _amadeus_get_monitored_leads(amadeus, latitude: float, longitude: float,
                                  radius: int, radius_unit: str) -> List[Dict]:
    """Get hotels using Amadeus API"""
    try:
        from amadeus import ResponseError

        hotel_list = amadeus.reference_data.locations.hotels.by_geocode.get(
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            radiusUnit=radius_unit
        )
        if not hotel_list.data:
            return []
        return [{'hotel': {'name': h['name'].title(), 'hotelId': h['hotelId']}}
                for h in hotel_list.data]
    except Exception as e:
        print(f"Amadeus API Error: {e}")
        return []


def _amadeus_get_hotel_offers(amadeus, hotel_ids: List[str], check_in: str,
                               check_out: str, adults: int) -> List[Dict]:
    """Get hotel offers using Amadeus API"""
    hotel_ids = hotel_ids[:20]

    try:
        from amadeus import ResponseError

        response = amadeus.shopping.hotel_offers_search.get(
            hotelIds=','.join(hotel_ids),
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=adults,
            currency='USD'
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"Amadeus Hotel Offers Error: {e}")
        return []


def _amadeus_get_pricing_range(amadeus, hotel_id: str, days: int,
                                adults: int) -> pd.DataFrame:
    """Get pricing range using Amadeus API (one call per day)"""
    today = datetime.date.today()
    data = []

    for day_offset in range(days):
        check_in = today + datetime.timedelta(days=day_offset)
        check_out = check_in + datetime.timedelta(days=1)

        try:
            response = amadeus.shopping.hotel_offers_search.get(
                hotelIds=hotel_id,
                checkInDate=check_in.isoformat(),
                checkOutDate=check_out.isoformat(),
                adults=adults,
                currency='USD'
            )

            if response.data:
                for hotel in response.data:
                    hotel_name = hotel.get('hotel', {}).get('name', 'Unknown')

                    for offer in hotel.get('offers', []):
                        room = offer.get('room', {})
                        price_info = offer.get('price', {})

                        room_type = room.get('typeEstimated', {}).get('category', 'Standard')
                        beds = room.get('typeEstimated', {}).get('beds', 1)
                        bed_type = room.get('typeEstimated', {}).get('bedType', 'Unknown')

                        total_price = float(price_info.get('total', 0))
                        currency = price_info.get('currency', 'USD')

                        policies = offer.get('policies', {})
                        cancellation = policies.get('cancellation', {})
                        available = offer.get('available', True)

                        data.append({
                            "Date": check_in,
                            "Hotel": hotel_name,
                            "Room Type": f"{room_type} ({beds} {bed_type})",
                            "Rate": total_price,
                            "Rate_Display": f"${total_price:.0f}",
                            "Currency": currency,
                            "Available": "✅ Available" if available else "❌ Sold Out",
                            "Cancellation": cancellation.get('type', 'Unknown')
                        })

        except Exception:
            pass

    return pd.DataFrame(data) if data else pd.DataFrame()


def _amadeus_60_day_insight(amadeus, hotel_id: str) -> pd.DataFrame:
    """60-day insight using Amadeus API"""
    try:
        from amadeus import ResponseError

        today = datetime.date.today()
        check_in = today.isoformat()
        check_out = (today + datetime.timedelta(days=1)).isoformat()

        response = amadeus.shopping.hotel_offers_search.get(
            hotelIds=hotel_id,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=2,
            currency='USD'
        )

        if response.data:
            return _amadeus_get_pricing_range(amadeus, hotel_id, days=60, adults=2)

    except Exception as e:
        print(f"Using simulated data (Amadeus: {e})")

    return _generate_simulated_data(hotel_id, days=60)


def _amadeus_search_by_city(amadeus, city_code: str, radius: int) -> List[Dict]:
    """Search hotels by city using Amadeus"""
    try:
        from amadeus import ResponseError

        response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code,
            radius=radius,
            radiusUnit='KM'
        )
        if response.data:
            return [{'hotel': {'name': h['name'].title(), 'hotelId': h['hotelId']}}
                    for h in response.data]
    except Exception as e:
        print(f"Amadeus city search error: {e}")

    return []


# ============================================
# SIMULATED DATA (FALLBACK)
# ============================================

def _generate_simulated_data(hotel_id: str, days: int = 60) -> pd.DataFrame:
    """
    Generate simulated pricing data for demo/testing.
    Uses realistic pricing patterns based on hotel type.
    """
    import random

    today = datetime.date.today()
    dates = [today + datetime.timedelta(days=x) for x in range(days)]

    categories = {
        "Classic Guest Room": {"base": 350, "variance": 50},
        "Superior King": {"base": 450, "variance": 75},
        "Oceanfront Suite": {"base": 850, "variance": 150}
    }

    data = []
    for d in dates:
        for cat, pricing in categories.items():
            is_weekend = d.weekday() >= 4
            weekend_factor = 1.4 if is_weekend else 1.0

            month = d.month
            if month in [6, 7, 8, 12]:
                season_factor = 1.3
            elif month in [3, 4]:
                season_factor = 1.2
            else:
                season_factor = 1.0

            days_out = (d - today).days
            if days_out <= 7:
                lead_factor = 1.15
            elif days_out <= 14:
                lead_factor = 1.05
            else:
                lead_factor = 1.0

            base = pricing["base"]
            variance = random.uniform(-pricing["variance"], pricing["variance"])
            price = (base + variance) * weekend_factor * season_factor * lead_factor

            base_availability = random.randint(0, 15)
            if is_weekend:
                base_availability = max(0, base_availability - 5)
            if season_factor > 1.1:
                base_availability = max(0, base_availability - 3)

            data.append({
                "Date": d,
                "Unit Type": cat,
                "Rooms Available": base_availability,
                "Target Units": 10,
                "Rate_Float": round(price, 2),
                "Rate": f"${int(price)}",
                "Availability Status": "✅ 10+ Units" if base_availability >= 10 else "❌ Limited"
            })

    return pd.DataFrame(data)
