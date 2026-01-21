"""
Casita PMS Lite - Revenue Management Dashboard
Dynamic pricing and property management for vacation rentals.

Run with: streamlit run pms_app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import sqlite3
import bcrypt
import os
from dotenv import load_dotenv

# Import Casita PMS modules
from casita_pms import CasitaPMS, get_pms_instance
from guesty_api import GuestyAPI, get_guesty_client
from ai_bot import CasitaAIBot, get_ai_bot

load_dotenv()

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Casita PMS",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (Casita branding) ---
st.markdown("""
<style>
    /* Primary Orange accent */
    .stButton > button[kind="primary"] {
        background-color: #FF6B35;
        border-color: #FF6B35;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #E55A2B;
        border-color: #E55A2B;
    }

    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: #1a1a2e;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE & AUTH ---
def verify_user(email, password):
    """Verify user credentials"""
    try:
        conn = sqlite3.connect('casita.db')
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE email=?", (email,))
        result = c.fetchone()
        conn.close()

        if result:
            stored_hash = result[0]
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except:
        pass
    return False

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'pms' not in st.session_state:
    st.session_state.pms = get_pms_instance()
if 'selected_property_id' not in st.session_state:
    st.session_state.selected_property_id = None
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'dashboard'

pms = st.session_state.pms

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("src/Casita_Logo_Black&Orange-01transparent.png", width=350)
        st.markdown("### Revenue Management System")
        st.markdown("---")

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="team@casita.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In", use_container_width=True, type="primary")

            if submit:
                if verify_user(email, password):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    st.stop()

# --- TOP NAVIGATION BAR ---
# Professional header with logo, nav, and user info aligned
st.markdown("""
<style>
    .nav-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 2px solid #FF6B35;
        margin-bottom: 1rem;
    }
    .nav-buttons {
        display: flex;
        gap: 0.5rem;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Single row header
header_cols = st.columns([1.5, 5, 2])

with header_cols[0]:
    st.image("src/Casita_Logo_Black&Orange-01transparent.png", width=140)

with header_cols[1]:
    # Navigation buttons in a row
    nav_cols = st.columns(5)

    with nav_cols[0]:
        if st.button("💰 Revenue", use_container_width=True,
                     type="primary" if st.session_state.current_view == 'revenue' else "secondary"):
            st.session_state.current_view = 'revenue'
            st.rerun()

    with nav_cols[1]:
        if st.button("🤖 CasitAI", use_container_width=True,
                     type="primary" if st.session_state.current_view == 'aibot' else "secondary"):
            st.session_state.current_view = 'aibot'
            st.rerun()

    with nav_cols[2]:
        if st.button("🔍 Amadeus", use_container_width=True,
                     type="primary" if st.session_state.current_view == 'amadeus' else "secondary"):
            st.session_state.current_view = 'amadeus'
            st.rerun()

    with nav_cols[3]:
        if st.button("📈 Analytics", use_container_width=True,
                     type="primary" if st.session_state.current_view == 'analytics' else "secondary"):
            st.session_state.current_view = 'analytics'
            st.rerun()

    with nav_cols[4]:
        if st.button("🔄 Sync", use_container_width=True):
            with st.spinner("Syncing..."):
                try:
                    guesty = get_guesty_client()
                    stats = guesty.sync_to_casita_pms(pms)
                    st.toast(f"Synced {stats['properties']} properties, {stats['units']} units")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {str(e)}")

with header_cols[2]:
    # User info and property selector
    user_prop_cols = st.columns([2, 1])

    with user_prop_cols[0]:
        # Property Selector
        properties = pms.get_all_properties()
        if properties:
            property_names = {p['id']: p['name'] for p in properties}
            selected_id = st.selectbox(
                "Property",
                options=list(property_names.keys()),
                format_func=lambda x: property_names[x],
                index=0 if st.session_state.selected_property_id is None else
                      list(property_names.keys()).index(st.session_state.selected_property_id)
                      if st.session_state.selected_property_id in property_names else 0,
                label_visibility="collapsed"
            )
            st.session_state.selected_property_id = selected_id
        else:
            st.selectbox("Property", options=["No properties"], disabled=True, label_visibility="collapsed")
            st.session_state.selected_property_id = None

    with user_prop_cols[1]:
        if st.button("🚪", key="logout_top", help=f"Logout ({st.session_state.get('user_email', 'User')})"):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.rerun()

st.markdown("---")

# --- MAIN CONTENT ---

# ============================================
# REVENUE MANAGEMENT VIEW (Main Dashboard)
# ============================================
if st.session_state.current_view == 'revenue' or st.session_state.current_view == 'dashboard':
    st.title("💰 Revenue Management")

    # Sub-tabs for Revenue Management
    rev_tab1, rev_tab2, rev_tab3, rev_tab4 = st.tabs(["Dashboard", "Properties", "Pricing Rules", "Calendar"])

    if st.session_state.selected_property_id:
        prop = pms.get_property(st.session_state.selected_property_id)
        units = pms.get_units_by_property(st.session_state.selected_property_id)

        # Property Header
        st.markdown(f"## {prop['name']}")

        # Key Metrics Row
        col1, col2, col3, col4, col5 = st.columns(5)

        metrics = pms.calculate_metrics(st.session_state.selected_property_id)

        with col1:
            st.metric("Total Units", len(units))
        with col2:
            st.metric("Occupancy", f"{metrics['occupancy_rate']}%")
        with col3:
            st.metric("ADR", f"${metrics['adr']:.2f}")
        with col4:
            st.metric("RevPAR", f"${metrics['revpar']:.2f}")
        with col5:
            st.metric("Base Price", f"${prop['base_price'] or 0:.2f}")

        st.markdown("---")

        # Smart Pricing Status
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 📈 Full Year Price Forecast (365 Days)")

            if units:
                # Generate pricing calendar for first unit - FULL YEAR
                unit = units[0]
                calendar = pms.generate_pricing_calendar(unit['id'], days=365)

                if calendar:
                    df = pd.DataFrame(calendar)
                    df['date'] = pd.to_datetime(df['date'])
                    df['month'] = df['date'].dt.to_period('M')

                    # Monthly average for cleaner visualization
                    monthly_df = df.groupby('month').agg({
                        'base_price': 'mean',
                        'final_price': 'mean'
                    }).reset_index()
                    monthly_df['month'] = monthly_df['month'].astype(str)

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df['date'],
                        y=df['base_price'],
                        name='Base Price',
                        line=dict(color='#888888', dash='dash')
                    ))
                    fig.add_trace(go.Scatter(
                        x=df['date'],
                        y=df['final_price'],
                        name='Final Price',
                        line=dict(color='#FF6B35', width=2),
                        fill='tonexty',
                        fillcolor='rgba(255, 107, 53, 0.1)'
                    ))

                    fig.update_layout(
                        title=f"Pricing: {unit['unit_name']} (Full Year)",
                        xaxis_title="Date",
                        yaxis_title="Price ($)",
                        hovermode='x unified',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Yearly summary stats
                    st.markdown("**Yearly Summary**")
                    sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
                    with sum_col1:
                        st.metric("Avg Price", f"${df['final_price'].mean():.2f}")
                    with sum_col2:
                        st.metric("Min Price", f"${df['final_price'].min():.2f}")
                    with sum_col3:
                        st.metric("Max Price", f"${df['final_price'].max():.2f}")
                    with sum_col4:
                        price_range = df['final_price'].max() - df['final_price'].min()
                        st.metric("Price Range", f"${price_range:.2f}")
            else:
                st.info("Add units to see pricing forecast")

        with col2:
            st.markdown("### 🔄 Smart Pricing Sync")

            # Manual sync input
            with st.form("sync_form"):
                st.markdown("**Update from Airbnb Smart Pricing**")
                new_price = st.number_input("Current Smart Price ($)",
                                            value=float(prop['base_price'] or 0),
                                            min_value=0.0, step=10.0)
                demand_score = st.slider("Demand Score", 1, 100, 50)

                if st.form_submit_button("Sync Price", use_container_width=True, type="primary"):
                    pms.sync_smart_pricing(st.session_state.selected_property_id,
                                          new_price, demand_score)
                    st.success(f"Synced ${new_price:.2f} to all units!")
                    st.rerun()

            # Sync history
            st.markdown("**Recent Syncs**")
            history = pms.get_smart_pricing_history(st.session_state.selected_property_id, days=7)
            if history:
                for h in history[:5]:
                    st.text(f"${h['smart_price']} - {h['sync_date']}")
            else:
                st.text("No sync history")

        st.markdown("---")

        # Units Overview
        st.markdown("### 🏨 Units Overview")

        if units:
            unit_data = []
            for u in units:
                # Get today's price
                price_info = pms.calculate_price(u['id'], date.today())
                unit_data.append({
                    'Unit': u['unit_name'],
                    'Type': u['unit_type'] or 'Standard',
                    'Modifier': f"{u['price_modifier'] or 0:+.0f}%",
                    'Today\'s Price': f"${price_info['final_price']:.2f}" if price_info else 'N/A',
                    'Status': '🟢 Active' if u['is_active'] else '🔴 Inactive'
                })

            st.dataframe(pd.DataFrame(unit_data), use_container_width=True, hide_index=True)
        else:
            st.info("No units configured. Go to Properties to add units.")

    else:
        st.info("👈 Select a property from the sidebar or create one in Properties")

# ============================================
# PROPERTIES VIEW
# ============================================
elif st.session_state.current_view == 'properties':
    st.title("🏠 Property Management")

    tab1, tab2 = st.tabs(["All Properties", "Add New Property"])

    with tab1:
        properties = pms.get_all_properties(active_only=False)

        if properties:
            for prop in properties:
                with st.expander(f"**{prop['name']}** ({prop['nickname'] or 'No nickname'})", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"""
                        **Location:** {prop['city'] or 'N/A'}, {prop['state'] or 'N/A'}
                        **Type:** {prop['property_type'] or 'MTL'}
                        **Base Price:** ${prop['base_price'] or 0:.2f}
                        **Min/Max:** ${prop['min_price'] or 0:.2f} - ${prop['max_price'] or 999:.2f}
                        """)

                    with col2:
                        # Units for this property
                        units = pms.get_units_by_property(prop['id'])
                        st.markdown(f"**Units:** {len(units)}")

                        if st.button(f"Manage Units", key=f"manage_{prop['id']}"):
                            st.session_state.selected_property_id = prop['id']
                            st.session_state.manage_property = prop['id']

                    # Show units if managing
                    if st.session_state.get('manage_property') == prop['id']:
                        st.markdown("---")
                        st.markdown("#### Units")

                        for u in units:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            with col1:
                                st.text(f"{u['unit_name']} ({u['unit_type'] or 'Standard'})")
                            with col2:
                                st.text(f"Modifier: {u['price_modifier'] or 0:+.0f}%")
                            with col3:
                                new_mod = st.number_input("Mod", value=float(u['price_modifier'] or 0),
                                                         key=f"mod_{u['id']}", label_visibility="collapsed")
                                if new_mod != (u['price_modifier'] or 0):
                                    pms.set_unit_price_modifier(u['id'], new_mod)

                        # Add unit form
                        st.markdown("**Add New Unit**")
                        with st.form(f"add_unit_{prop['id']}"):
                            ucol1, ucol2, ucol3 = st.columns(3)
                            with ucol1:
                                unit_name = st.text_input("Unit Name", placeholder="Suite 101")
                            with ucol2:
                                unit_type = st.selectbox("Type", ["Oceanfront Suite", "Superior King",
                                                                   "Classic Room", "Economy", "Custom"])
                            with ucol3:
                                modifier = st.number_input("Price Modifier %", value=0.0, step=5.0)

                            if st.form_submit_button("Add Unit", type="primary"):
                                if unit_name:
                                    pms.create_unit(prop['id'], unit_name,
                                                   unit_type=unit_type,
                                                   price_modifier=modifier)
                                    st.success(f"Added {unit_name}")
                                    st.rerun()
        else:
            st.info("No properties yet. Create one below!")

    with tab2:
        st.markdown("### Create New Property")

        with st.form("new_property"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Property Name*", placeholder="South Beach Suites")
                nickname = st.text_input("Nickname", placeholder="SBS")
                city = st.text_input("City", placeholder="Miami Beach")
                state = st.text_input("State", placeholder="FL")

            with col2:
                base_price = st.number_input("Base Price ($)", value=200.0, min_value=0.0, step=10.0)
                min_price = st.number_input("Minimum Price ($)", value=100.0, min_value=0.0, step=10.0)
                max_price = st.number_input("Maximum Price ($)", value=500.0, min_value=0.0, step=10.0)
                airbnb_id = st.text_input("Airbnb Listing ID (optional)")

            if st.form_submit_button("Create Property", type="primary", use_container_width=True):
                if name:
                    prop_id = pms.create_property(
                        name=name,
                        nickname=nickname,
                        city=city,
                        state=state,
                        base_price=base_price,
                        min_price=min_price,
                        max_price=max_price,
                        airbnb_listing_id=airbnb_id if airbnb_id else None
                    )
                    st.success(f"Created property: {name} (ID: {prop_id})")
                    st.session_state.selected_property_id = prop_id
                    st.rerun()
                else:
                    st.error("Property name is required")

# ============================================
# PRICING RULES VIEW
# ============================================
elif st.session_state.current_view == 'pricing':
    st.title("💰 Pricing Rules")

    if not st.session_state.selected_property_id:
        st.warning("Please select a property from the sidebar")
        st.stop()

    prop = pms.get_property(st.session_state.selected_property_id)
    st.markdown(f"### Rules for: {prop['name']}")

    tab1, tab2, tab3, tab4 = st.tabs(["Day of Week", "Seasonal", "Last Minute", "Orphan Days"])

    with tab1:
        st.markdown("#### Weekend & Weekday Adjustments")
        st.markdown("Set price adjustments for each day of the week (e.g., +20% on Saturdays)")

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        with st.form("dow_pricing"):
            cols = st.columns(7)
            adjustments = []

            for i, day in enumerate(days):
                with cols[i]:
                    st.markdown(f"**{day[:3]}**")
                    adj = st.number_input(f"{day}", value=0.0 if i < 4 else (15.0 if i == 4 else 20.0),
                                         step=5.0, key=f"dow_{i}", label_visibility="collapsed")
                    adjustments.append(adj)

            if st.form_submit_button("Save Day of Week Rules", type="primary", use_container_width=True):
                for i, adj in enumerate(adjustments):
                    pms.add_day_of_week_pricing(st.session_state.selected_property_id, i, adj)
                st.success("Day of week pricing saved!")

    with tab2:
        st.markdown("#### Seasonal Pricing Periods")
        st.markdown("Define high/low season price adjustments")

        with st.form("seasonal_pricing"):
            col1, col2 = st.columns(2)

            with col1:
                season_name = st.text_input("Season Name", placeholder="Summer Peak")
                start_date = st.date_input("Start Date", value=date(2026, 6, 1))
                end_date = st.date_input("End Date", value=date(2026, 8, 31))

            with col2:
                adjustment = st.number_input("Adjustment %", value=25.0, step=5.0)
                min_nights = st.number_input("Min Nights (optional)", value=2, min_value=1)

            if st.form_submit_button("Add Seasonal Rule", type="primary"):
                if season_name:
                    pms.add_seasonal_pricing(
                        st.session_state.selected_property_id,
                        season_name,
                        start_date.isoformat(),
                        end_date.isoformat(),
                        adjustment,
                        min_nights=min_nights
                    )
                    st.success(f"Added {season_name}: {adjustment:+.0f}%")

    with tab3:
        st.markdown("#### Last Minute Discounts")
        st.markdown("Automatically discount prices close to check-in date")

        with st.form("last_minute"):
            col1, col2 = st.columns(2)

            with col1:
                days_before = st.number_input("Days Before Check-in", value=3, min_value=1, max_value=30)
            with col2:
                discount = st.number_input("Discount %", value=10.0, min_value=0.0, max_value=50.0, step=5.0)

            if st.form_submit_button("Add Last Minute Discount", type="primary"):
                pms.add_last_minute_discount(st.session_state.selected_property_id, days_before, discount)
                st.success(f"Added {discount}% discount for bookings within {days_before} days")

    with tab4:
        st.markdown("#### Orphan Day Management")
        st.markdown("Discount gap nights between bookings to fill calendar holes")

        with st.form("orphan_days"):
            col1, col2 = st.columns(2)

            with col1:
                gap_nights = st.number_input("Gap Size (nights)", value=1, min_value=1, max_value=5)
            with col2:
                discount = st.number_input("Discount %", value=15.0, min_value=0.0, max_value=50.0, step=5.0,
                                          key="orphan_discount")

            reduce_min = st.checkbox("Also reduce minimum stay requirement", value=True)

            if st.form_submit_button("Add Orphan Day Rule", type="primary"):
                pms.add_orphan_day_pricing(st.session_state.selected_property_id, gap_nights, discount, reduce_min)
                st.success(f"Added {discount}% discount for {gap_nights}-night gaps")

# ============================================
# CALENDAR VIEW
# ============================================
elif st.session_state.current_view == 'calendar':
    st.title("📅 Pricing Calendar")

    if not st.session_state.selected_property_id:
        st.warning("Please select a property from the sidebar")
        st.stop()

    prop = pms.get_property(st.session_state.selected_property_id)
    units = pms.get_units_by_property(st.session_state.selected_property_id)

    if units:
        # Calendar controls
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # Unit selector
            unit_names = {u['id']: u['unit_name'] for u in units}
            selected_unit = st.selectbox("Select Unit", options=list(unit_names.keys()),
                                         format_func=lambda x: unit_names[x])

        with col2:
            # Time range selector
            calendar_range = st.selectbox("Calendar Range", [
                "Full Year (365 days)",
                "6 Months (180 days)",
                "3 Months (90 days)",
                "2 Months (60 days)",
                "1 Month (30 days)"
            ], index=0)

            range_map = {
                "Full Year (365 days)": 365,
                "6 Months (180 days)": 180,
                "3 Months (90 days)": 90,
                "2 Months (60 days)": 60,
                "1 Month (30 days)": 30
            }
            days_to_show = range_map[calendar_range]

        with col3:
            # Year selector for yearly view
            current_year = date.today().year
            selected_year = st.selectbox("Year", [current_year, current_year + 1], index=0)

        st.markdown(f"### {prop['name']} - {calendar_range}")

        # Generate calendar (full year by default)
        calendar = pms.generate_pricing_calendar(selected_unit, days=days_to_show)

        if calendar:
            df = pd.DataFrame(calendar)
            df['date'] = pd.to_datetime(df['date'])
            df['day_name'] = df['date'].dt.day_name()

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Avg Price", f"${df['final_price'].mean():.2f}")
            with col2:
                st.metric("Min Price", f"${df['final_price'].min():.2f}")
            with col3:
                st.metric("Max Price", f"${df['final_price'].max():.2f}")
            with col4:
                weekend_avg = df[df['day_name'].isin(['Friday', 'Saturday', 'Sunday'])]['final_price'].mean()
                st.metric("Weekend Avg", f"${weekend_avg:.2f}")

            # Calendar heatmap
            st.markdown("### Price Heatmap")

            fig = px.imshow(
                df.pivot_table(index=df['date'].dt.isocalendar().week,
                              columns=df['date'].dt.dayofweek,
                              values='final_price',
                              aggfunc='mean').values,
                labels=dict(x="Day of Week", y="Week", color="Price ($)"),
                x=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                color_continuous_scale='YlOrRd'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Detailed table
            st.markdown("### Daily Breakdown")

            display_df = df[['date', 'day_name', 'base_price', 'final_price']].copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df.columns = ['Date', 'Day', 'Base Price', 'Final Price']

            # Add adjustment breakdown
            adj_df = pd.json_normalize(df['adjustments'])
            display_df = pd.concat([display_df.reset_index(drop=True), adj_df], axis=1)

            st.dataframe(display_df, use_container_width=True, hide_index=True,
                        column_config={
                            'Base Price': st.column_config.NumberColumn(format="$%.2f"),
                            'Final Price': st.column_config.NumberColumn(format="$%.2f"),
                            'seasonal': st.column_config.NumberColumn("Seasonal", format="$%.2f"),
                            'day_of_week': st.column_config.NumberColumn("DOW", format="$%.2f"),
                            'last_minute': st.column_config.NumberColumn("Last Min", format="$%.2f"),
                        })
    else:
        st.info("No units configured for this property")

# ============================================
# ANALYTICS VIEW
# ============================================
elif st.session_state.current_view == 'analytics':
    st.title("📈 Analytics")

    # Sub-tabs for Analytics
    analytics_tab1, analytics_tab2 = st.tabs(["Portfolio Analytics", "Guesty Listings"])

    with analytics_tab2:
        st.markdown("### 🔗 Guesty Listings")

        guesty_id = os.getenv('GUESTY_CLIENT_ID', '')
        if guesty_id:
            st.success("✅ Guesty API Connected")

            if st.button("📥 Fetch Listings from Guesty", type="primary"):
                with st.spinner("Fetching listings from Guesty..."):
                    try:
                        guesty = get_guesty_client()
                        listings = guesty.get_all_listings(limit=100)

                        if listings:
                            st.success(f"Found {len(listings)} listings in Guesty")

                            # Display listings
                            listing_data = []
                            for l in listings:
                                prices = l.get('prices', {})
                                address = l.get('address', {})
                                listing_data.append({
                                    'Name': l.get('title', 'N/A'),
                                    'Type': l.get('type', 'SINGLE'),
                                    'City': address.get('city', 'N/A'),
                                    'Bedrooms': l.get('bedrooms', 0),
                                    'Base Price': f"${prices.get('basePrice', 0):.2f}",
                                    'Status': '🟢 Active' if l.get('active') else '🔴 Inactive'
                                })

                            st.dataframe(pd.DataFrame(listing_data), use_container_width=True, hide_index=True)

                            # Sync option
                            st.markdown("---")
                            if st.button("🔄 Sync All to Casita PMS", type="primary"):
                                with st.spinner("Syncing to PMS..."):
                                    stats = guesty.sync_to_casita_pms(pms)
                                    st.success(f"Synced {stats['properties']} properties, {stats['units']} units!")
                                    if stats['errors']:
                                        with st.expander("View Errors"):
                                            for err in stats['errors']:
                                                st.text(err)
                                    st.rerun()
                        else:
                            st.info("No listings found in Guesty")

                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        else:
            st.warning("⚠️ Guesty credentials not found in .env")

    with analytics_tab1:
        if not st.session_state.selected_property_id:
            st.warning("Please select a property from the sidebar")
            st.stop()

        prop = pms.get_property(st.session_state.selected_property_id)
        st.markdown(f"### {prop['name']} - Performance Analytics")

    # Date range selector - Full year options
    col1, col2 = st.columns(2)
    with col1:
        time_period = st.selectbox("Time Period", [
            "Full Year (365 days)",
            "6 Months (180 days)",
            "3 Months (90 days)",
            "2 Months (60 days)",
            "1 Month (30 days)",
            "2 Weeks (14 days)",
            "1 Week (7 days)"
        ], index=0)

        period_map = {
            "Full Year (365 days)": 365,
            "6 Months (180 days)": 180,
            "3 Months (90 days)": 90,
            "2 Months (60 days)": 60,
            "1 Month (30 days)": 30,
            "2 Weeks (14 days)": 14,
            "1 Week (7 days)": 7
        }
        days_back = period_map[time_period]

    # Generate forecast data - full year by default
    forecast = pms.get_occupancy_forecast(st.session_state.selected_property_id, days=days_back)

    if forecast:
        df = pd.DataFrame(forecast)
        df['date'] = pd.to_datetime(df['date'])

        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Occupancy", f"{df['occupancy_rate'].mean():.1f}%")
        with col2:
            st.metric("Avg ADR", f"${df['adr'].mean():.2f}")
        with col3:
            st.metric("Avg RevPAR", f"${df['revpar'].mean():.2f}")
        with col4:
            st.metric("Total Revenue", f"${df['daily_revenue'].sum():.2f}")

        st.markdown("---")

        # Charts
        col1, col2 = st.columns(2)

        with col1:
            fig_occ = px.area(df, x='date', y='occupancy_rate',
                             title='Occupancy Rate (%)',
                             color_discrete_sequence=['#FF6B35'])
            fig_occ.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig_occ, use_container_width=True)

        with col2:
            fig_rev = px.bar(df, x='date', y='daily_revenue',
                            title='Daily Revenue ($)',
                            color_discrete_sequence=['#0078D4'])
            st.plotly_chart(fig_rev, use_container_width=True)

        # RevPAR trend
        fig_revpar = px.line(df, x='date', y=['adr', 'revpar'],
                            title='ADR vs RevPAR',
                            color_discrete_map={'adr': '#FF6B35', 'revpar': '#0078D4'})
        st.plotly_chart(fig_revpar, use_container_width=True)
    else:
        st.info("No analytics data available yet")

# ============================================
# CASITAI CS BOT VIEW
# ============================================
elif st.session_state.current_view == 'aibot':
    st.title("🤖 CasitAI CS Bot")

    st.markdown("""
    Intelligent guest communication assistant with:
    - **Saved Replies First** - Matches guest inquiries to your Guesty saved responses
    - **Web Info** - Weather, events, transportation queries (>75% effectiveness)
    - **Smart Escalation** - Negative tone or low confidence → assigns to CS Agent
    - **Per-Listing Control** - Enable/disable bot for specific listings
    """)

    # Check system status
    try:
        guesty = get_guesty_client()
        ai_bot = get_ai_bot(guesty)
        status = ai_bot.get_status()

        # Status indicators
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if status['ollama_available']:
                st.success("✅ Ollama Running")
            else:
                st.error("❌ Ollama Offline")

        with col2:
            if status['model_ready']:
                st.success(f"✅ Model: {status['default_model']}")
            else:
                st.warning(f"⚠️ Model not found")

        with col3:
            if status['guesty_connected']:
                st.success("✅ Guesty Connected")
            else:
                st.error("❌ Guesty Offline")

        with col4:
            st.info(f"📝 {status['saved_replies_count']} Saved Replies")

        st.markdown("---")

        # Main tabs
        bot_tab1, bot_tab2, bot_tab3, bot_tab4 = st.tabs(["Listings", "Test Bot", "Conversations", "Settings"])

        with bot_tab1:
            st.markdown("### 🏠 Bot Activation by Listing")
            st.markdown("Enable or disable the CasitAI bot for each listing. Parent listings (MTL) can be toggled to affect all child listings, or you can control individual units.")

            # Initialize enabled listings in session state
            if 'bot_enabled_listings' not in st.session_state:
                st.session_state.bot_enabled_listings = set()
            if 'bot_enabled_parents' not in st.session_state:
                st.session_state.bot_enabled_parents = set()

            try:
                # AUTO-SYNC: Automatically fetch listings when page loads
                if 'casitai_listings_synced' not in st.session_state:
                    with st.spinner("Syncing listings from Guesty..."):
                        listings = ai_bot.get_all_listings(force_refresh=True)
                        st.session_state.casitai_listings_synced = True
                        st.session_state.cached_listings = listings
                else:
                    listings = st.session_state.get('cached_listings', [])
                    if not listings:
                        listings = ai_bot.get_all_listings(force_refresh=True)
                        st.session_state.cached_listings = listings

                if listings:
                    st.success(f"Found {len(listings)} listings in Guesty")

                    # Organize listings by parent/child hierarchy
                    parent_listings = []
                    child_listings = {}  # parent_id -> [children]
                    single_listings = []

                    for l in listings:
                        listing_type = l.get('type', 'SINGLE')
                        if listing_type == 'MTL':
                            parent_listings.append(l)
                            child_listings[l.get('_id', '')] = []
                        elif listing_type == 'MTL_CHILD':
                            parent_id = l.get('parentId', l.get('parent', {}).get('_id', ''))
                            if parent_id not in child_listings:
                                child_listings[parent_id] = []
                            child_listings[parent_id].append(l)
                        else:
                            single_listings.append(l)

                    # Enable/Disable All buttons
                    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
                    with btn_col1:
                        if st.button("✅ Enable All", type="primary"):
                            for l in listings:
                                lid = l.get('_id', '')
                                if lid:
                                    ai_bot.enable_bot_for_listing(lid)
                                    st.session_state.bot_enabled_listings.add(lid)
                            for parent in parent_listings:
                                st.session_state.bot_enabled_parents.add(parent.get('_id', ''))
                            st.rerun()
                    with btn_col2:
                        if st.button("❌ Disable All"):
                            for l in listings:
                                lid = l.get('_id', '')
                                if lid:
                                    ai_bot.disable_bot_for_listing(lid)
                            st.session_state.bot_enabled_listings.clear()
                            st.session_state.bot_enabled_parents.clear()
                            st.rerun()
                    with btn_col3:
                        if st.button("🔄 Refresh Listings"):
                            st.session_state.casitai_listings_synced = False
                            st.rerun()

                    st.markdown("---")

                    # Display Parent Listings (MTL) with expandable children
                    if parent_listings:
                        st.markdown("#### 🏢 Parent Listings (MTL)")
                        st.caption("Toggle parent to affect all child units, or expand to control individual units")

                        for parent in parent_listings:
                            parent_id = parent.get('_id', '')
                            parent_name = parent.get('title', 'Unnamed Parent')
                            children = child_listings.get(parent_id, [])
                            is_parent_enabled = parent_id in st.session_state.bot_enabled_parents

                            # Parent listing row
                            pcol1, pcol2, pcol3 = st.columns([3, 1, 1])

                            with pcol1:
                                st.markdown(f"**🏢 {parent_name}** (MTL - {len(children)} units)")

                            with pcol2:
                                if is_parent_enabled:
                                    st.success("🟢 All Active")
                                else:
                                    # Check if any children are individually enabled
                                    active_children = sum(1 for c in children if c.get('_id', '') in st.session_state.bot_enabled_listings)
                                    if active_children > 0:
                                        st.warning(f"🟡 {active_children}/{len(children)}")
                                    else:
                                        st.text("⚪ Inactive")

                            with pcol3:
                                if is_parent_enabled:
                                    if st.button("Disable All", key=f"disable_parent_{parent_id}"):
                                        st.session_state.bot_enabled_parents.discard(parent_id)
                                        for child in children:
                                            cid = child.get('_id', '')
                                            ai_bot.disable_bot_for_listing(cid)
                                            st.session_state.bot_enabled_listings.discard(cid)
                                        st.rerun()
                                else:
                                    if st.button("Enable All", key=f"enable_parent_{parent_id}", type="primary"):
                                        st.session_state.bot_enabled_parents.add(parent_id)
                                        for child in children:
                                            cid = child.get('_id', '')
                                            ai_bot.enable_bot_for_listing(cid)
                                            st.session_state.bot_enabled_listings.add(cid)
                                        st.rerun()

                            # Expandable section for individual child units
                            if children:
                                with st.expander(f"View {len(children)} units"):
                                    for child in children:
                                        child_id = child.get('_id', '')
                                        child_name = child.get('title', 'Unnamed Unit')
                                        is_child_enabled = child_id in st.session_state.bot_enabled_listings

                                        ccol1, ccol2, ccol3 = st.columns([3, 1, 1])

                                        with ccol1:
                                            st.markdown(f"└─ {child_name}")

                                        with ccol2:
                                            if is_child_enabled:
                                                st.success("🟢")
                                            else:
                                                st.text("⚪")

                                        with ccol3:
                                            if is_child_enabled:
                                                if st.button("Off", key=f"disable_{child_id}"):
                                                    ai_bot.disable_bot_for_listing(child_id)
                                                    st.session_state.bot_enabled_listings.discard(child_id)
                                                    # Update parent status
                                                    st.session_state.bot_enabled_parents.discard(parent_id)
                                                    st.rerun()
                                            else:
                                                if st.button("On", key=f"enable_{child_id}", type="primary"):
                                                    ai_bot.enable_bot_for_listing(child_id)
                                                    st.session_state.bot_enabled_listings.add(child_id)
                                                    st.rerun()

                        st.markdown("---")

                    # Display Single Listings (not part of MTL)
                    if single_listings:
                        st.markdown("#### 🏠 Individual Listings")

                        for listing in single_listings:
                            listing_id = listing.get('_id', '')
                            listing_name = listing.get('title', 'Unnamed')
                            listing_type = listing.get('type', 'SINGLE')
                            is_enabled = listing_id in st.session_state.bot_enabled_listings

                            col1, col2, col3 = st.columns([3, 1, 1])

                            with col1:
                                st.markdown(f"**{listing_name}** ({listing_type})")

                            with col2:
                                if is_enabled:
                                    st.success("🟢 Active")
                                else:
                                    st.text("⚪ Inactive")

                            with col3:
                                if is_enabled:
                                    if st.button("Disable", key=f"disable_{listing_id}"):
                                        ai_bot.disable_bot_for_listing(listing_id)
                                        st.session_state.bot_enabled_listings.discard(listing_id)
                                        st.rerun()
                                else:
                                    if st.button("Enable", key=f"enable_{listing_id}", type="primary"):
                                        ai_bot.enable_bot_for_listing(listing_id)
                                        st.session_state.bot_enabled_listings.add(listing_id)
                                        st.rerun()

                    st.markdown("---")
                    total_enabled = len(st.session_state.bot_enabled_listings)
                    st.info(f"**{total_enabled}** listings with bot enabled")

                else:
                    st.warning("No listings found in Guesty. Please check your API credentials.")

            except Exception as e:
                st.error(f"Error loading listings: {str(e)}")

        with bot_tab2:
            st.markdown("### 💬 Test CasitAI Response")
            st.markdown("Enter a guest message to see how the bot would respond:")

            test_message = st.text_area(
                "Guest Message",
                placeholder="Example: What time is check-in? Is there parking available?",
                height=100
            )

            col1, col2 = st.columns([1, 3])
            with col1:
                test_btn = st.button("🤖 Generate Response", type="primary", use_container_width=True)

            if test_btn and test_message:
                with st.spinner("Processing with CasitAI..."):
                    result = ai_bot.test_response(test_message)

                    # Show source indicator
                    source = result.get('source', 'unknown')
                    if source == 'saved_reply':
                        st.success(f"✅ **Matched Saved Reply**: {result.get('matched_reply_title', 'N/A')}")
                    elif source == 'web_info':
                        st.info("🌐 **Web Info Response** (weather/events/transportation)")
                    elif source == 'escalated':
                        st.error(f"🚨 **Escalated to CS Agent**: {result.get('reason', 'N/A')}")
                    elif source == 'ai':
                        st.info("🤖 **AI Generated Response**")

                    if result.get('assigned_to_agent'):
                        st.warning("⚠️ **Will be assigned to Customer Service Agent**")

                    if result.get('response'):
                        st.markdown("**Response:**")
                        st.info(result['response'])

                    # Show metadata
                    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
                    with meta_col1:
                        st.metric("Confidence", f"{result['confidence']:.0%}")
                    with meta_col2:
                        st.metric("Source", source.replace('_', ' ').title())
                    with meta_col3:
                        st.metric("Sentiment", result.get('sentiment', 'neutral').title())
                    with meta_col4:
                        st.metric("Escalated", "Yes" if result['escalated'] else "No")

            # Quick test examples
            st.markdown("---")
            st.markdown("**Quick Test Examples:**")
            example_col1, example_col2, example_col3, example_col4 = st.columns(4)

            with example_col1:
                if st.button("Check-in time?", use_container_width=True):
                    st.session_state.test_msg = "What time is check-in?"
                    st.rerun()

            with example_col2:
                if st.button("Weather forecast?", use_container_width=True):
                    st.session_state.test_msg = "What's the weather like this weekend?"
                    st.rerun()

            with example_col3:
                if st.button("Negative: Terrible!", use_container_width=True):
                    st.session_state.test_msg = "This place is terrible and disgusting!"
                    st.rerun()

            with example_col4:
                if st.button("Refund request", use_container_width=True):
                    st.session_state.test_msg = "I want a refund for my stay"
                    st.rerun()

        with bot_tab3:
            st.markdown("### 📥 Guest Conversations")
            st.markdown("Recent conversations from Guesty inbox:")

            if st.button("🔄 Refresh Conversations", type="primary"):
                st.rerun()

            try:
                conversations = guesty.get_conversations(limit=20)

                if conversations:
                    for conv in conversations[:10]:
                        guest_name = conv.get('guest', {}).get('fullName', 'Unknown Guest')
                        listing_name = conv.get('listing', {}).get('title', 'Unknown Listing')
                        last_message = conv.get('lastMessage', {}).get('body', '')[:100]
                        conv_id = conv.get('_id', '')

                        with st.expander(f"**{guest_name}** - {listing_name}"):
                            st.text(f"Last message: {last_message}...")
                            st.text(f"Conversation ID: {conv_id}")

                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("View Messages", key=f"view_{conv_id}"):
                                    messages = guesty.get_conversation_messages(conv_id, limit=10)
                                    for msg in messages:
                                        sender = "🧑 Guest" if msg.get('from') == 'guest' else "🏠 Host"
                                        st.markdown(f"**{sender}:** {msg.get('body', '')[:200]}")

                            with col2:
                                if st.button("Generate Reply", key=f"reply_{conv_id}"):
                                    messages = guesty.get_conversation_messages(conv_id, limit=5)
                                    if messages:
                                        latest = messages[0].get('body', '')
                                        result = ai_bot.test_response(latest)
                                        if result.get('response'):
                                            st.info(f"**Suggested Reply:** {result['response']}")
                else:
                    st.info("No conversations found")

            except Exception as e:
                st.error(f"Error loading conversations: {str(e)}")

        with bot_tab4:
            st.markdown("### ⚙️ CasitAI Bot Settings")

            # Settings sub-tabs
            settings_tab1, settings_tab2, settings_tab3 = st.tabs(["Configuration", "Knowledge Base", "Training Data"])

            with settings_tab1:
                st.markdown("**Ollama Configuration**")
                st.text(f"URL: {status['ollama_url']}")
                st.text(f"Default Model: {status['default_model']}")

                if status['available_models']:
                    st.markdown("**Available Models:**")
                    for model in status['available_models']:
                        st.text(f"  • {model}")
                else:
                    st.warning("No models found. Run: `ollama pull llama3`")

                st.markdown("---")

                st.markdown("**Escalation Settings**")
                st.text(f"Confidence Threshold: {status['confidence_threshold']:.0%}")
                st.text("Auto-escalate: refund, cancel, complaint, emergency, urgent, manager, legal, etc.")

                st.markdown("---")

                st.markdown("**Bot Personality**")
                st.info("CasitAI is configured to be casual but professional - like a friendly local who knows hospitality. The bot understands standard hotel practices like check-in times, luggage storage, and quiet hours.")

            with settings_tab2:
                st.markdown("**Saved Replies (Knowledge Base)**")
                st.caption("These are pulled from your Guesty saved replies and used to answer common questions.")

                if st.button("🔄 Refresh Saved Replies"):
                    replies = guesty.get_saved_replies(limit=50)
                    st.success(f"Loaded {len(replies)} saved replies")

                    if replies:
                        for reply in replies[:10]:
                            title = reply.get('title', reply.get('name', 'Untitled'))
                            category = reply.get('category', 'General')
                            st.text(f"  • {title} ({category})")

            with settings_tab3:
                st.markdown("**Conversation Training**")
                st.caption("Load your team's past conversations to teach CasitAI how you communicate with guests.")

                # Training status
                col1, col2 = st.columns(2)
                with col1:
                    if status.get('training_loaded'):
                        st.success(f"✅ {status.get('training_examples', 0)} training examples loaded")
                    else:
                        st.info("No training data loaded yet")

                with col2:
                    st.text(f"Saved Replies: {status.get('saved_replies_count', 0)}")

                st.markdown("---")

                st.markdown("**Load Conversation History**")
                st.caption("Pull all past conversations from Guesty to train the bot on your team's communication style.")

                train_col1, train_col2 = st.columns([1, 2])
                with train_col1:
                    num_conversations = st.number_input("Max conversations", min_value=50, max_value=1000, value=200, step=50)

                with train_col2:
                    st.caption("More conversations = better training but takes longer to load")

                if st.button("📚 Load Training Data", type="primary", use_container_width=True):
                    with st.spinner(f"Loading up to {num_conversations} conversations from Guesty..."):
                        try:
                            examples = ai_bot.load_all_conversations(limit=num_conversations, force_refresh=True)
                            training_stats = ai_bot.get_training_stats()

                            if examples:
                                st.success(f"Loaded {len(examples)} training examples from {training_stats.get('unique_conversations', 0)} conversations")

                                if training_stats.get('sample_topics'):
                                    st.markdown("**Common Topics Found:**")
                                    for topic in training_stats['sample_topics']:
                                        st.text(f"  • {topic}")

                                # Show sample examples
                                st.markdown("---")
                                st.markdown("**Sample Training Examples:**")
                                for i, example in enumerate(examples[:3]):
                                    with st.expander(f"Example {i+1}: Guest Question"):
                                        st.markdown(f"**Guest:** {example['guest_message'][:200]}...")
                                        st.markdown(f"**Your Team's Response:** {example['host_response'][:300]}...")
                            else:
                                st.warning("No conversation history found or Guesty API issue. Try again later.")

                        except Exception as e:
                            st.error(f"Error loading training data: {str(e)}")

                st.markdown("---")
                st.info("💡 Training data helps CasitAI match your team's communication style. The bot will use similar phrasing and tone as your past responses.")

    except Exception as e:
        st.error(f"Error initializing AI Bot: {str(e)}")
        st.markdown("""
        **Setup Requirements:**
        1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
        2. Pull a model: `ollama pull llama3.2`
        3. Ensure Guesty credentials are in `.env`
        """)

# ============================================
# AMADEUS WATCHER VIEW
# ============================================
elif st.session_state.current_view == 'amadeus':
    st.title("🔍 Amadeus Price Watcher")

    st.markdown("### Competitor Price Intelligence")

    # Check if Amadeus credentials exist
    amadeus_id = os.getenv('AMADEUS_CLIENT_ID', '')
    amadeus_secret = os.getenv('AMADEUS_CLIENT_SECRET', '')

    if amadeus_id and amadeus_secret:
        st.success("✅ Amadeus API Connected")

        # Import and use Amadeus
        try:
            from amadeus import Client
            import hotel_intel

            amadeus = Client(client_id=amadeus_id, client_secret=amadeus_secret, hostname='production')

            st.markdown("---")

            # Search area config
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Search Area: South Beach, Miami**")
                st.text("Latitude: 25.7826")
                st.text("Longitude: -80.1340")
                st.text("Radius: 5 KM")

            with col2:
                if st.button("🔄 Refresh Hotel List", type="primary"):
                    st.rerun()

            st.markdown("---")

            # Get hotels from Amadeus
            st.markdown("### 🏨 Competitor Hotels in Area")
            with st.spinner("Fetching hotels from Amadeus..."):
                hotels = hotel_intel.get_monitored_leads(amadeus)

            if hotels:
                st.success(f"Found {len(hotels)} hotels in the area")

                # Display hotels
                for hotel in hotels:
                    h_name = hotel['hotel']['name']
                    h_id = hotel['hotel']['hotelId']

                    with st.expander(f"**{h_name}**"):
                        st.text(f"Hotel ID: {h_id}")

                        # Get 60-day insight
                        if st.button(f"View Pricing", key=f"view_{h_id}"):
                            df = hotel_intel.get_60_day_insight(amadeus, h_id)
                            if not df.empty:
                                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No hotels found or API error occurred")

        except Exception as e:
            st.error(f"Error connecting to Amadeus: {str(e)}")

    else:
        st.warning("⚠️ Amadeus credentials not found in .env")
        st.markdown("""
        **To enable Amadeus Watcher:**
        1. Get API credentials from [Amadeus for Developers](https://developers.amadeus.com)
        2. Add to your `.env` file:
        ```
        AMADEUS_CLIENT_ID=your_client_id
        AMADEUS_CLIENT_SECRET=your_client_secret
        ```
        """)

# --- FOOTER ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>Casita PMS Lite v1.0 | Powered by Airbnb Smart Pricing</div>",
    unsafe_allow_html=True
)
