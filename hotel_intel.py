"""
Hotel Intelligence Module
Real hotel pricing and availability data for competitor analysis.

Features:
- Hotel discovery by location (geocode)
- Real-time hotel offers/pricing
- 60-day pricing forecast
- Competitor set tracking
"""

import datetime
import pandas as pd
from typing import List, Dict
from amadeus import ResponseError


def get_monitored_leads(amadeus, latitude: float = 25.7826, longitude: float = -80.1340,
                        radius: int = 5, radius_unit: str = 'KM') -> List[Dict]:
    """
    Finds all hotels in a given area via Geocode.

    Args:
        amadeus: Amadeus client instance
        latitude: Center point latitude (default: South Beach)
        longitude: Center point longitude (default: South Beach)
        radius: Search radius
        radius_unit: 'KM' or 'MILE'

    Returns:
        List of hotel objects with name and hotelId
    """
    try:
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
    except ResponseError as e:
        print(f"Amadeus API Error: {e.description if hasattr(e, 'description') else str(e)}")
        return []
    except Exception as e:
        print(f"Discovery Error: {e}")
        return []


def get_hotel_offers(amadeus, hotel_ids: List[str], check_in: str = "",
                     check_out: str = "", adults: int = 2) -> List[Dict]:
    """
    Get real hotel offers/pricing from Amadeus.

    Args:
        amadeus: Amadeus client instance
        hotel_ids: List of hotel IDs to query (max 20 at a time)
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

    # Amadeus limits to 20 hotels per request
    hotel_ids = hotel_ids[:20]

    try:
        response = amadeus.shopping.hotel_offers_search.get(
            hotelIds=','.join(hotel_ids),
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=adults,
            currency='USD'
        )
        return response.data if response.data else []

    except ResponseError as e:
        print(f"Hotel Offers API Error: {e.description if hasattr(e, 'description') else str(e)}")
        return []
    except Exception as e:
        print(f"Hotel Offers Error: {e}")
        return []


def get_hotel_pricing_range(amadeus, hotel_id: str, days: int = 60,
                            adults: int = 2) -> pd.DataFrame:
    """
    Get pricing data for a hotel over a date range.
    Queries Amadeus API for each date to build pricing forecast.

    Args:
        amadeus: Amadeus client instance
        hotel_id: Single hotel ID
        days: Number of days to query (default 60)
        adults: Number of adults

    Returns:
        DataFrame with date, room types, rates, availability
    """
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

                        # Availability indicator
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

        except ResponseError as e:
            # Log but continue - some dates may not have availability
            pass
        except Exception as e:
            print(f"Error fetching {check_in}: {e}")

    return pd.DataFrame(data) if data else pd.DataFrame()


def get_60_day_insight(amadeus, hotel_id: str) -> pd.DataFrame:
    """
    60-Day pricing insight for a specific hotel.
    Uses real Amadeus API when available, falls back to simulation.

    Args:
        amadeus: Amadeus client instance
        hotel_id: Hotel ID to query

    Returns:
        DataFrame with pricing data
    """
    # First try real API
    try:
        today = datetime.date.today()
        check_in = today.isoformat()
        check_out = (today + datetime.timedelta(days=1)).isoformat()

        # Test if hotel offers API is accessible
        response = amadeus.shopping.hotel_offers_search.get(
            hotelIds=hotel_id,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=2,
            currency='USD'
        )

        if response.data:
            # Real API works - get full 60-day data
            return get_hotel_pricing_range(amadeus, hotel_id, days=60)

    except ResponseError as e:
        # API not available or rate limited - use simulation
        print(f"Using simulated data (API: {e.description if hasattr(e, 'description') else str(e)})")
    except Exception as e:
        print(f"Using simulated data: {e}")

    # Fallback: Simulated data for demo/development
    return _generate_simulated_data(hotel_id, days=60)


def _generate_simulated_data(hotel_id: str, days: int = 60) -> pd.DataFrame:
    """
    Generate simulated pricing data for demo/testing.
    Uses realistic pricing patterns based on hotel type.
    """
    import random

    today = datetime.date.today()
    dates = [today + datetime.timedelta(days=x) for x in range(days)]

    # Room categories with base pricing
    categories = {
        "Classic Guest Room": {"base": 350, "variance": 50},
        "Superior King": {"base": 450, "variance": 75},
        "Oceanfront Suite": {"base": 850, "variance": 150}
    }

    data = []
    for d in dates:
        for cat, pricing in categories.items():
            # Day of week factor (weekends more expensive)
            is_weekend = d.weekday() >= 4  # Fri, Sat, Sun
            weekend_factor = 1.4 if is_weekend else 1.0

            # Seasonality factor (simplified)
            month = d.month
            if month in [6, 7, 8, 12]:  # Summer + December peak
                season_factor = 1.3
            elif month in [3, 4]:  # Spring break
                season_factor = 1.2
            else:
                season_factor = 1.0

            # Lead time factor (prices often higher closer to date)
            days_out = (d - today).days
            if days_out <= 7:
                lead_factor = 1.15
            elif days_out <= 14:
                lead_factor = 1.05
            else:
                lead_factor = 1.0

            # Calculate price with variance
            base = pricing["base"]
            variance = random.uniform(-pricing["variance"], pricing["variance"])
            price = (base + variance) * weekend_factor * season_factor * lead_factor

            # Availability simulation (lower availability on weekends/peak)
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


def get_comp_set_summary(amadeus, hotel_ids: List[str], check_in: str = "") -> pd.DataFrame:
    """
    Get competitive set pricing summary for a specific date.

    Args:
        amadeus: Amadeus client instance
        hotel_ids: List of competitor hotel IDs
        check_in: Date to check (defaults to today)

    Returns:
        DataFrame with hotel pricing comparison
    """
    if not check_in:
        check_in = datetime.date.today().isoformat()

    check_out = (datetime.date.fromisoformat(check_in) + datetime.timedelta(days=1)).isoformat()

    offers = get_hotel_offers(amadeus, hotel_ids, check_in, check_out)

    if not offers:
        return pd.DataFrame()

    summary = []
    for hotel in offers:
        hotel_name = hotel.get('hotel', {}).get('name', 'Unknown')
        hotel_id = hotel.get('hotel', {}).get('hotelId', '')

        # Get lowest and highest rates
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


def search_hotels_by_city(amadeus, city_code: str, radius: int = 20) -> List[Dict]:
    """
    Search hotels by IATA city code.

    Args:
        amadeus: Amadeus client instance
        city_code: IATA city code (e.g., 'MIA' for Miami)
        radius: Search radius in KM

    Returns:
        List of hotels
    """
    try:
        response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code,
            radius=radius,
            radiusUnit='KM'
        )
        if response.data:
            return [{'hotel': {'name': h['name'].title(), 'hotelId': h['hotelId']}}
                    for h in response.data]
    except ResponseError as e:
        print(f"City search error: {e}")
    except Exception as e:
        print(f"Search error: {e}")

    return []
