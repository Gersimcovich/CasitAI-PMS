import datetime
import pandas as pd
import random
from amadeus import ResponseError

def get_monitored_leads(amadeus):
    """
    Finds all hotels in South Beach (5km radius) via Geocode.
    """
    try:
        hotel_list = amadeus.reference_data.locations.hotels.by_geocode.get(
            latitude=25.7826,
            longitude=-80.1340,
            radius=5,
            radiusUnit='KM'
        )
        if not hotel_list.data:
            return []
        return [{'hotel': {'name': h['name'].title(), 'hotelId': h['hotelId']}} 
                for h in hotel_list.data]
    except Exception as e:
        print(f"Discovery Error: {e}")
        return []

def get_60_day_insight(amadeus, hotel_id):
    """
    60-Day Data: Focuses strictly on physical Rooms Available and Rate.
    Targeting the 10-unit availability threshold.
    """
    today = datetime.date.today()
    dates = [today + datetime.timedelta(days=x) for x in range(60)]
    categories = ["Oceanfront Suite", "Superior King", "Classic Guest Room"]
    
    data = []
    for d in dates:
        for cat in categories:
            # Simulated Inventory (0 to 15 rooms)
            # A value of 10+ means the 'Double-Call' test passed
            rooms_left = random.randint(0, 15) 
            
            # Simulated Pricing
            is_weekend = d.weekday() >= 4
            base = 450 if "Suite" not in cat else 950
            price = base * (1.6 if is_weekend else 1.0)

            data.append({
                "Date": d,
                "Unit Type": cat,
                "Rooms Available": rooms_left,
                "Target Units": 10,
                "Rate_Float": round(price, 2),
                "Rate": f"${int(price)}",
                "Availability Status": "✅ 10+ Units" if rooms_left >= 10 else "❌ Limited"
            })
            
    return pd.DataFrame(data)