-- Casita PMS Lite - Revenue Management Focused
-- Database Schema v1.0

-- ============================================
-- CORE ENTITIES
-- ============================================

-- Properties (Parent Listings)
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    nickname VARCHAR(100),
    property_type VARCHAR(50) DEFAULT 'MTL',  -- MTL (Multi-Unit) or SINGLE
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Airbnb Connection
    airbnb_listing_id VARCHAR(100),
    airbnb_ical_url TEXT,
    smart_pricing_enabled BOOLEAN DEFAULT TRUE,

    -- Base Pricing (from Airbnb Smart Pricing)
    base_price DECIMAL(10, 2),
    min_price DECIMAL(10, 2),
    max_price DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',

    -- Property Details
    bedrooms INTEGER,
    bathrooms DECIMAL(3, 1),
    max_guests INTEGER,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Units (Child Listings) - Linked to Parent Properties
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    unit_name VARCHAR(255) NOT NULL,
    unit_number VARCHAR(50),

    -- Pricing Inheritance
    inherit_parent_pricing BOOLEAN DEFAULT TRUE,
    price_modifier DECIMAL(5, 2) DEFAULT 0.00,  -- +/- percentage from parent
    price_modifier_type VARCHAR(10) DEFAULT 'percent',  -- 'percent' or 'fixed'

    -- Unit-specific overrides (used when inherit_parent_pricing = FALSE)
    custom_base_price DECIMAL(10, 2),
    custom_min_price DECIMAL(10, 2),
    custom_max_price DECIMAL(10, 2),

    -- Airbnb Connection (if listed separately)
    airbnb_listing_id VARCHAR(100),

    -- Unit Details
    unit_type VARCHAR(100),  -- 'Oceanfront Suite', 'Standard King', etc.
    bedrooms INTEGER,
    bathrooms DECIMAL(3, 1),
    max_guests INTEGER,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- ============================================
-- REVENUE MANAGEMENT
-- ============================================

-- Smart Pricing Sync Log (from Airbnb)
CREATE TABLE IF NOT EXISTS smart_pricing_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    sync_date DATE NOT NULL,
    smart_price DECIMAL(10, 2),
    demand_score INTEGER,  -- 1-100 demand indicator
    sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'success',
    raw_response TEXT,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    UNIQUE(property_id, sync_date)
);

-- Daily Pricing Calendar (Computed prices after rules applied)
CREATE TABLE IF NOT EXISTS pricing_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    calendar_date DATE NOT NULL,

    -- Pricing Breakdown
    base_price DECIMAL(10, 2),           -- From parent/smart pricing
    adjusted_price DECIMAL(10, 2),        -- After rules applied
    final_price DECIMAL(10, 2),           -- Published price

    -- Price Components
    seasonal_adjustment DECIMAL(10, 2) DEFAULT 0,
    day_of_week_adjustment DECIMAL(10, 2) DEFAULT 0,
    last_minute_adjustment DECIMAL(10, 2) DEFAULT 0,
    occupancy_adjustment DECIMAL(10, 2) DEFAULT 0,
    event_adjustment DECIMAL(10, 2) DEFAULT 0,

    -- Availability
    is_available BOOLEAN DEFAULT TRUE,
    is_blocked BOOLEAN DEFAULT FALSE,
    block_reason VARCHAR(100),

    -- Minimum Stay
    min_nights INTEGER DEFAULT 1,

    -- Status
    price_source VARCHAR(50) DEFAULT 'smart_pricing',  -- 'smart_pricing', 'manual', 'rule'
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
    UNIQUE(unit_id, calendar_date)
);

-- ============================================
-- PRICING RULES ENGINE (PriceLabs-style)
-- ============================================

-- Pricing Rules
CREATE TABLE IF NOT EXISTS pricing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,  -- NULL = applies to all properties
    unit_id INTEGER,      -- NULL = applies to all units of property
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,

    -- Rule Types:
    -- 'seasonal' - Date range based
    -- 'day_of_week' - Mon-Sun adjustments
    -- 'last_minute' - X days before check-in
    -- 'far_out' - X days in advance
    -- 'orphan_day' - Gap day pricing
    -- 'occupancy' - Based on occupancy %
    -- 'event' - Local events/holidays

    -- Adjustment
    adjustment_type VARCHAR(10) NOT NULL,  -- 'percent' or 'fixed'
    adjustment_value DECIMAL(10, 2) NOT NULL,

    -- Conditions (JSON for flexibility)
    conditions TEXT,  -- JSON: {"start_date": "2026-06-01", "end_date": "2026-08-31"}

    -- Priority (higher = applied later)
    priority INTEGER DEFAULT 0,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
);

-- Day of Week Defaults (Quick setup for weekend premiums, etc.)
CREATE TABLE IF NOT EXISTS day_of_week_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,  -- 0=Monday, 6=Sunday
    adjustment_type VARCHAR(10) DEFAULT 'percent',
    adjustment_value DECIMAL(10, 2) DEFAULT 0,
    min_nights INTEGER DEFAULT 1,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    UNIQUE(property_id, day_of_week)
);

-- Seasonal Pricing Periods
CREATE TABLE IF NOT EXISTS seasonal_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    season_name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    adjustment_type VARCHAR(10) DEFAULT 'percent',
    adjustment_value DECIMAL(10, 2) NOT NULL,
    min_nights INTEGER,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- Last Minute Discounts
CREATE TABLE IF NOT EXISTS last_minute_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    days_before_checkin INTEGER NOT NULL,  -- e.g., 7, 3, 1
    adjustment_type VARCHAR(10) DEFAULT 'percent',
    adjustment_value DECIMAL(10, 2) NOT NULL,  -- Usually negative for discount

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- Far Out Pricing (Book early premiums/discounts)
CREATE TABLE IF NOT EXISTS far_out_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    days_in_advance INTEGER NOT NULL,  -- e.g., 90, 180, 365
    adjustment_type VARCHAR(10) DEFAULT 'percent',
    adjustment_value DECIMAL(10, 2) NOT NULL,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- Orphan Day Management (Gap nights between bookings)
CREATE TABLE IF NOT EXISTS orphan_day_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    gap_nights INTEGER NOT NULL,  -- 1, 2, 3 night gaps
    adjustment_type VARCHAR(10) DEFAULT 'percent',
    adjustment_value DECIMAL(10, 2) NOT NULL,  -- Usually discount
    reduce_min_stay BOOLEAN DEFAULT TRUE,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- ============================================
-- RESERVATIONS & BOOKINGS
-- ============================================

CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,

    -- Guest Info
    guest_name VARCHAR(255),
    guest_email VARCHAR(255),
    guest_phone VARCHAR(50),
    num_guests INTEGER,

    -- Dates
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    nights INTEGER,

    -- Pricing
    nightly_rate DECIMAL(10, 2),
    total_price DECIMAL(10, 2),
    cleaning_fee DECIMAL(10, 2) DEFAULT 0,
    service_fee DECIMAL(10, 2) DEFAULT 0,

    -- Source
    booking_source VARCHAR(50),  -- 'airbnb', 'vrbo', 'direct', 'booking.com'
    external_reservation_id VARCHAR(100),

    -- Status
    status VARCHAR(50) DEFAULT 'confirmed',  -- 'pending', 'confirmed', 'cancelled', 'completed'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
);

-- ============================================
-- ANALYTICS & REPORTING
-- ============================================

-- Daily Performance Metrics
CREATE TABLE IF NOT EXISTS daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    metric_date DATE NOT NULL,

    -- Occupancy
    total_units INTEGER,
    occupied_units INTEGER,
    occupancy_rate DECIMAL(5, 2),

    -- Revenue
    total_revenue DECIMAL(10, 2),
    adr DECIMAL(10, 2),  -- Average Daily Rate
    revpar DECIMAL(10, 2),  -- Revenue Per Available Room

    -- Bookings
    new_bookings INTEGER DEFAULT 0,
    cancellations INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    UNIQUE(property_id, metric_date)
);

-- Comp Set (Competitor Tracking)
CREATE TABLE IF NOT EXISTS comp_set (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    competitor_name VARCHAR(255) NOT NULL,
    competitor_airbnb_id VARCHAR(100),
    competitor_url TEXT,
    notes TEXT,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

-- Competitor Price Tracking
CREATE TABLE IF NOT EXISTS comp_pricing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comp_set_id INTEGER NOT NULL,
    tracked_date DATE NOT NULL,
    price DECIMAL(10, 2),
    is_available BOOLEAN,
    min_nights INTEGER,

    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (comp_set_id) REFERENCES comp_set(id) ON DELETE CASCADE
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_units_property ON units(property_id);
CREATE INDEX IF NOT EXISTS idx_pricing_calendar_date ON pricing_calendar(calendar_date);
CREATE INDEX IF NOT EXISTS idx_pricing_calendar_unit_date ON pricing_calendar(unit_id, calendar_date);
CREATE INDEX IF NOT EXISTS idx_reservations_dates ON reservations(check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_reservations_unit ON reservations(unit_id);
CREATE INDEX IF NOT EXISTS idx_smart_pricing_date ON smart_pricing_sync(property_id, sync_date);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(property_id, metric_date);
