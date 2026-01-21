"""
Casita PMS Lite - Revenue Management Module
Dynamic pricing engine for vacation rental portfolio management.

Features:
- Parent/Child listing price cascade
- Smart pricing sync via channel manager
- Seasonal adjustments
- Day of week pricing
- Last minute discounts
- Orphan day management
- Portfolio analytics
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import os


class CasitaPMS:
    """Core PMS class for Casita Revenue Management"""

    # Calendar horizon - always open full year ahead
    DEFAULT_CALENDAR_DAYS = 365
    MAX_CALENDAR_DAYS = 730  # Up to 2 years

    def __init__(self, db_path: str = "casita_pms.db"):
        self.db_path = db_path
        self._init_database()

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database with schema"""
        schema_path = os.path.join(os.path.dirname(__file__), "casita_pms_schema.sql")
        if os.path.exists(schema_path):
            conn = self._get_connection()
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())
            conn.commit()
            conn.close()

    # ============================================
    # PROPERTY MANAGEMENT (Parent Listings)
    # ============================================

    def create_property(self, name: str, **kwargs) -> int:
        """Create a new parent property/listing"""
        conn = self._get_connection()
        cursor = conn.cursor()

        fields = ['name'] + list(kwargs.keys())
        placeholders = ['?'] * len(fields)
        values = [name] + list(kwargs.values())

        sql = f"INSERT INTO properties ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql, values)
        property_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return property_id

    def get_property(self, property_id: int) -> Optional[Dict]:
        """Get property by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_properties(self, active_only: bool = True) -> List[Dict]:
        """Get all properties"""
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM properties"
        if active_only:
            sql += " WHERE is_active = 1"
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_property_pricing(self, property_id: int, base_price: float,
                                 min_price: float = None, max_price: float = None):
        """Update parent property base pricing (from Airbnb Smart Pricing)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE properties
            SET base_price = ?, min_price = ?, max_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (base_price, min_price, max_price, property_id))
        conn.commit()
        conn.close()

        # Cascade to child units
        self._cascade_pricing_to_units(property_id)

    # ============================================
    # UNIT MANAGEMENT (Child Listings)
    # ============================================

    def create_unit(self, property_id: int, unit_name: str, **kwargs) -> int:
        """Create a child unit under a parent property"""
        conn = self._get_connection()
        cursor = conn.cursor()

        fields = ['property_id', 'unit_name'] + list(kwargs.keys())
        placeholders = ['?'] * len(fields)
        values = [property_id, unit_name] + list(kwargs.values())

        sql = f"INSERT INTO units ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql, values)
        unit_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return unit_id

    def get_units_by_property(self, property_id: int) -> List[Dict]:
        """Get all units for a property"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM units WHERE property_id = ? AND is_active = 1", (property_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def set_unit_price_modifier(self, unit_id: int, modifier: float,
                                 modifier_type: str = 'percent'):
        """Set price modifier for a child unit relative to parent"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE units
            SET price_modifier = ?, price_modifier_type = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (modifier, modifier_type, unit_id))
        conn.commit()
        conn.close()

    def _cascade_pricing_to_units(self, property_id: int):
        """Cascade parent pricing to all child units"""
        property_data = self.get_property(property_id)
        if not property_data:
            return

        base_price = property_data['base_price']
        units = self.get_units_by_property(property_id)

        for unit in units:
            if unit['inherit_parent_pricing']:
                # Calculate unit price based on modifier
                modifier = unit['price_modifier'] or 0
                modifier_type = unit['price_modifier_type']

                if modifier_type == 'percent':
                    unit_price = base_price * (1 + modifier / 100)
                else:  # fixed
                    unit_price = base_price + modifier

                # Update unit's effective price in calendar
                self._update_unit_calendar_base_price(unit['id'], unit_price)

    # ============================================
    # PRICING RULES ENGINE
    # ============================================

    def add_seasonal_pricing(self, property_id: int, season_name: str,
                              start_date: str, end_date: str,
                              adjustment_value: float,
                              adjustment_type: str = 'percent',
                              min_nights: int = None) -> int:
        """Add seasonal pricing adjustment"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seasonal_pricing
            (property_id, season_name, start_date, end_date, adjustment_type, adjustment_value, min_nights)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (property_id, season_name, start_date, end_date, adjustment_type, adjustment_value, min_nights))
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return rule_id

    def add_day_of_week_pricing(self, property_id: int, day_of_week: int,
                                 adjustment_value: float,
                                 adjustment_type: str = 'percent',
                                 min_nights: int = 1):
        """Add day of week adjustment (0=Monday, 6=Sunday)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO day_of_week_pricing
            (property_id, day_of_week, adjustment_type, adjustment_value, min_nights)
            VALUES (?, ?, ?, ?, ?)
        """, (property_id, day_of_week, adjustment_type, adjustment_value, min_nights))
        conn.commit()
        conn.close()

    def add_last_minute_discount(self, property_id: int, days_before: int,
                                  discount_percent: float):
        """Add last minute discount (negative adjustment)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO last_minute_pricing
            (property_id, days_before_checkin, adjustment_type, adjustment_value)
            VALUES (?, ?, 'percent', ?)
        """, (property_id, days_before, -abs(discount_percent)))
        conn.commit()
        conn.close()

    def add_orphan_day_pricing(self, property_id: int, gap_nights: int,
                                discount_percent: float,
                                reduce_min_stay: bool = True):
        """Add orphan day discount for gap nights"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orphan_day_pricing
            (property_id, gap_nights, adjustment_type, adjustment_value, reduce_min_stay)
            VALUES (?, ?, 'percent', ?, ?)
        """, (property_id, gap_nights, -abs(discount_percent), reduce_min_stay))
        conn.commit()
        conn.close()

    # ============================================
    # PRICING CALCULATOR
    # ============================================

    def calculate_price(self, unit_id: int, target_date: date) -> Dict[str, Any]:
        """Calculate final price for a unit on a specific date"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get unit and parent property
        cursor.execute("""
            SELECT u.*, p.base_price as parent_base_price, p.min_price, p.max_price, p.id as property_id
            FROM units u
            JOIN properties p ON u.property_id = p.id
            WHERE u.id = ?
        """, (unit_id,))
        unit = cursor.fetchone()

        if not unit:
            conn.close()
            return None

        unit = dict(unit)
        property_id = unit['property_id']

        # Start with base price
        if unit['inherit_parent_pricing']:
            base_price = float(unit['parent_base_price'] or 0)
            # Apply unit modifier
            modifier = float(unit['price_modifier'] or 0)
            if unit['price_modifier_type'] == 'percent':
                base_price = base_price * (1 + modifier / 100)
            else:
                base_price = base_price + modifier
        else:
            base_price = float(unit['custom_base_price'] or 0)

        adjustments = {
            'base_price': base_price,
            'seasonal': 0,
            'day_of_week': 0,
            'last_minute': 0,
            'orphan_day': 0
        }

        # Apply seasonal adjustment
        cursor.execute("""
            SELECT * FROM seasonal_pricing
            WHERE property_id = ? AND start_date <= ? AND end_date >= ?
            ORDER BY adjustment_value DESC LIMIT 1
        """, (property_id, target_date.isoformat(), target_date.isoformat()))
        seasonal = cursor.fetchone()
        if seasonal:
            seasonal = dict(seasonal)
            if seasonal['adjustment_type'] == 'percent':
                adjustments['seasonal'] = base_price * (seasonal['adjustment_value'] / 100)
            else:
                adjustments['seasonal'] = seasonal['adjustment_value']

        # Apply day of week adjustment
        day_num = target_date.weekday()
        cursor.execute("""
            SELECT * FROM day_of_week_pricing
            WHERE property_id = ? AND day_of_week = ?
        """, (property_id, day_num))
        dow = cursor.fetchone()
        if dow:
            dow = dict(dow)
            if dow['adjustment_type'] == 'percent':
                adjustments['day_of_week'] = base_price * (dow['adjustment_value'] / 100)
            else:
                adjustments['day_of_week'] = dow['adjustment_value']

        # Apply last minute discount
        days_until = (target_date - date.today()).days
        if days_until >= 0:
            cursor.execute("""
                SELECT * FROM last_minute_pricing
                WHERE property_id = ? AND days_before_checkin >= ?
                ORDER BY days_before_checkin ASC LIMIT 1
            """, (property_id, days_until))
            last_min = cursor.fetchone()
            if last_min:
                last_min = dict(last_min)
                adjustments['last_minute'] = base_price * (last_min['adjustment_value'] / 100)

        conn.close()

        # Calculate final price
        adjusted_price = base_price + sum([
            adjustments['seasonal'],
            adjustments['day_of_week'],
            adjustments['last_minute'],
            adjustments['orphan_day']
        ])

        # Apply min/max bounds
        min_price = float(unit['min_price'] or 0)
        max_price = float(unit['max_price'] or 999999)

        final_price = max(min_price, min(max_price, adjusted_price))

        return {
            'unit_id': unit_id,
            'date': target_date.isoformat(),
            'base_price': round(base_price, 2),
            'adjustments': {k: round(v, 2) for k, v in adjustments.items() if k != 'base_price'},
            'adjusted_price': round(adjusted_price, 2),
            'final_price': round(final_price, 2),
            'price_source': 'smart_pricing' if unit['inherit_parent_pricing'] else 'manual'
        }

    def generate_pricing_calendar(self, unit_id: int, days: int = None,
                                     start_date: date = None, end_date: date = None) -> List[Dict]:
        """
        Generate pricing calendar.

        Args:
            unit_id: The unit to generate calendar for
            days: Number of days from today (default: 365 for full year)
            start_date: Optional start date (default: today)
            end_date: Optional end date (overrides days if provided)
        """
        if days is None:
            days = self.DEFAULT_CALENDAR_DAYS

        if start_date is None:
            start_date = date.today()

        if end_date is not None:
            days = (end_date - start_date).days + 1

        # Cap at max calendar days
        days = min(days, self.MAX_CALENDAR_DAYS)

        calendar = []
        for i in range(days):
            target_date = start_date + timedelta(days=i)
            price_data = self.calculate_price(unit_id, target_date)
            if price_data:
                calendar.append(price_data)
        return calendar

    def generate_yearly_calendar(self, unit_id: int, year: int = None) -> List[Dict]:
        """Generate full year calendar for a specific year"""
        if year is None:
            year = date.today().year

        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # If start date is in the past, start from today
        if start_date < date.today():
            start_date = date.today()

        return self.generate_pricing_calendar(unit_id, start_date=start_date, end_date=end_date)

    def generate_monthly_calendar(self, unit_id: int, year: int, month: int) -> List[Dict]:
        """Generate calendar for a specific month"""
        from calendar import monthrange

        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        # If start date is in the past, start from today
        if start_date < date.today():
            start_date = date.today()
            if start_date > end_date:
                return []  # Month is entirely in the past

        return self.generate_pricing_calendar(unit_id, start_date=start_date, end_date=end_date)

    def _update_unit_calendar_base_price(self, unit_id: int, base_price: float):
        """Update calendar entries with new base price"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Update future dates
        cursor.execute("""
            UPDATE pricing_calendar
            SET base_price = ?, last_updated = CURRENT_TIMESTAMP
            WHERE unit_id = ? AND calendar_date >= date('now')
        """, (base_price, unit_id))
        conn.commit()
        conn.close()

    # ============================================
    # AIRBNB SMART PRICING SYNC
    # ============================================

    def sync_smart_pricing(self, property_id: int, smart_price: float,
                           demand_score: int = None):
        """Record smart pricing sync from Airbnb"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Record sync
        cursor.execute("""
            INSERT OR REPLACE INTO smart_pricing_sync
            (property_id, sync_date, smart_price, demand_score, sync_timestamp)
            VALUES (?, date('now'), ?, ?, CURRENT_TIMESTAMP)
        """, (property_id, smart_price, demand_score))

        # Update property base price
        cursor.execute("""
            UPDATE properties
            SET base_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (smart_price, property_id))

        conn.commit()
        conn.close()

        # Cascade to units
        self._cascade_pricing_to_units(property_id)

    def get_smart_pricing_history(self, property_id: int, days: int = 30) -> List[Dict]:
        """Get smart pricing history"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM smart_pricing_sync
            WHERE property_id = ? AND sync_date >= date('now', ?)
            ORDER BY sync_date DESC
        """, (property_id, f'-{days} days'))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ============================================
    # RESERVATIONS
    # ============================================

    def create_reservation(self, unit_id: int, check_in: str, check_out: str,
                           guest_name: str = None, **kwargs) -> int:
        """Create a reservation"""
        conn = self._get_connection()
        cursor = conn.cursor()

        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        nights = (check_out_date - check_in_date).days

        # Calculate total price
        total_price = 0
        for i in range(nights):
            day_date = check_in_date + timedelta(days=i)
            price_data = self.calculate_price(unit_id, day_date)
            if price_data:
                total_price += price_data['final_price']

        fields = ['unit_id', 'check_in', 'check_out', 'nights', 'total_price']
        values = [unit_id, check_in, check_out, nights, total_price]

        if guest_name:
            fields.append('guest_name')
            values.append(guest_name)

        for key, value in kwargs.items():
            fields.append(key)
            values.append(value)

        placeholders = ['?'] * len(fields)
        sql = f"INSERT INTO reservations ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql, values)
        reservation_id = cursor.lastrowid

        # Block calendar dates
        for i in range(nights):
            day_date = check_in_date + timedelta(days=i)
            cursor.execute("""
                INSERT OR REPLACE INTO pricing_calendar (unit_id, calendar_date, is_available, is_blocked, block_reason)
                VALUES (?, ?, 0, 1, 'reservation')
            """, (unit_id, day_date.isoformat()))

        conn.commit()
        conn.close()

        return reservation_id

    def get_reservations(self, unit_id: int = None, property_id: int = None,
                         start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get reservations with filters"""
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT r.*, u.unit_name, p.name as property_name
            FROM reservations r
            JOIN units u ON r.unit_id = u.id
            JOIN properties p ON u.property_id = p.id
            WHERE 1=1
        """
        params = []

        if unit_id:
            sql += " AND r.unit_id = ?"
            params.append(unit_id)
        if property_id:
            sql += " AND u.property_id = ?"
            params.append(property_id)
        if start_date:
            sql += " AND r.check_out >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND r.check_in <= ?"
            params.append(end_date)

        sql += " ORDER BY r.check_in"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ============================================
    # ANALYTICS
    # ============================================

    def calculate_metrics(self, property_id: int, metric_date: date = None) -> Dict:
        """Calculate daily performance metrics"""
        if metric_date is None:
            metric_date = date.today()

        conn = self._get_connection()
        cursor = conn.cursor()

        # Get total units
        cursor.execute("""
            SELECT COUNT(*) as total FROM units WHERE property_id = ? AND is_active = 1
        """, (property_id,))
        total_units = cursor.fetchone()['total']

        # Get occupied units
        cursor.execute("""
            SELECT COUNT(DISTINCT r.unit_id) as occupied
            FROM reservations r
            JOIN units u ON r.unit_id = u.id
            WHERE u.property_id = ? AND r.check_in <= ? AND r.check_out > ? AND r.status = 'confirmed'
        """, (property_id, metric_date.isoformat(), metric_date.isoformat()))
        occupied_units = cursor.fetchone()['occupied']

        # Get revenue for date
        cursor.execute("""
            SELECT SUM(r.total_price / r.nights) as daily_revenue
            FROM reservations r
            JOIN units u ON r.unit_id = u.id
            WHERE u.property_id = ? AND r.check_in <= ? AND r.check_out > ? AND r.status = 'confirmed'
        """, (property_id, metric_date.isoformat(), metric_date.isoformat()))
        revenue_row = cursor.fetchone()
        daily_revenue = revenue_row['daily_revenue'] or 0

        conn.close()

        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        adr = (daily_revenue / occupied_units) if occupied_units > 0 else 0
        revpar = (daily_revenue / total_units) if total_units > 0 else 0

        return {
            'property_id': property_id,
            'date': metric_date.isoformat(),
            'total_units': total_units,
            'occupied_units': occupied_units,
            'occupancy_rate': round(occupancy_rate, 2),
            'daily_revenue': round(daily_revenue, 2),
            'adr': round(adr, 2),
            'revpar': round(revpar, 2)
        }

    def get_occupancy_forecast(self, property_id: int, days: Optional[int] = None) -> List[Dict]:
        """Get occupancy forecast for next X days (default: full year)"""
        if days is None:
            days = self.DEFAULT_CALENDAR_DAYS

        forecast = []
        for i in range(days):
            forecast_date = date.today() + timedelta(days=i)
            metrics = self.calculate_metrics(property_id, forecast_date)
            forecast.append(metrics)
        return forecast

    def get_yearly_summary(self, property_id: int, year: Optional[int] = None) -> Dict:
        """Get yearly pricing and occupancy summary"""
        if year is None:
            year = date.today().year

        units = self.get_units_by_property(property_id)
        if not units:
            return {}

        # Generate full year calendar for first unit as reference
        calendar = self.generate_yearly_calendar(units[0]['id'], year)

        if not calendar:
            return {}

        prices = [day['final_price'] for day in calendar]

        # Group by month
        monthly_data = {}
        for day in calendar:
            month = day['date'][:7]  # YYYY-MM
            if month not in monthly_data:
                monthly_data[month] = []
            monthly_data[month].append(day['final_price'])

        monthly_avg = {month: sum(prices)/len(prices) for month, prices in monthly_data.items()}

        return {
            'year': year,
            'total_days': len(calendar),
            'avg_price': round(sum(prices) / len(prices), 2),
            'min_price': round(min(prices), 2),
            'max_price': round(max(prices), 2),
            'monthly_averages': {k: round(v, 2) for k, v in monthly_avg.items()}
        }


# ============================================
# STREAMLIT INTEGRATION HELPER
# ============================================

def get_pms_instance(db_path: str = None) -> CasitaPMS:
    """Get or create PMS instance for Streamlit"""
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "casita_pms.db")
    return CasitaPMS(db_path)


if __name__ == "__main__":
    # Quick test
    pms = CasitaPMS("casita_pms_test.db")

    # Create a parent property
    prop_id = pms.create_property(
        name="South Beach Suites",
        nickname="SBS",
        city="Miami Beach",
        state="FL",
        base_price=250.00,
        min_price=150.00,
        max_price=500.00
    )
    print(f"Created property: {prop_id}")

    # Create child units
    unit1 = pms.create_unit(prop_id, "Oceanfront Suite 101", unit_type="Oceanfront Suite", price_modifier=20)
    unit2 = pms.create_unit(prop_id, "Standard King 102", unit_type="Standard King", price_modifier=0)
    unit3 = pms.create_unit(prop_id, "Economy Room 103", unit_type="Economy", price_modifier=-15)
    print(f"Created units: {unit1}, {unit2}, {unit3}")

    # Add pricing rules
    pms.add_seasonal_pricing(prop_id, "Summer Peak", "2026-06-01", "2026-08-31", 30, "percent")
    pms.add_day_of_week_pricing(prop_id, 4, 15)  # Friday +15%
    pms.add_day_of_week_pricing(prop_id, 5, 20)  # Saturday +20%
    pms.add_last_minute_discount(prop_id, 3, 10)  # 10% off within 3 days
    pms.add_orphan_day_pricing(prop_id, 1, 15)  # 15% off single gap nights

    # Generate pricing calendar
    calendar = pms.generate_pricing_calendar(unit1, days=7)
    print("\nPricing Calendar for Oceanfront Suite 101:")
    for day in calendar:
        print(f"  {day['date']}: ${day['final_price']} (base: ${day['base_price']})")
