import streamlit as st
import pandas as pd
import plotly.express as px
from amadeus import Client
import filter_leads
import os
import sqlite3
import bcrypt
from dotenv import load_dotenv

load_dotenv()

# --- NEW: SECURITY LOGIC ---
def verify_user(email, password):
    conn = sqlite3.connect('casita.db')
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE email=?", (email,))
    result = c.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[0]
        # Check password against stored hash (bytes comparison)
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    return False

# --- UI: INITIAL STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False  # Set to False by default now

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    # Maintain your branding even on login
    st.image("src/Casita_Logo_Black&Orange-01.png", width=400, use_container_width=False)
    st.title("Team Access")
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log In", use_container_width=True)
        
        if submit:
            if verify_user(email, password):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.success("Access Granted")
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop() # Prevents the rest of the app from loading

# ... (Continue with your existing Amadeus and Dashboard code)

# --- UI: LOGO FIXED TOP LEFT (400px maintained) ---
top_col1, top_col2 = st.columns([1, 4])
with top_col1:
    st.image("src/Casita_Logo_Black&Orange-01.png", width=400, use_container_width=False)

# API Initialization
client_id = os.getenv('AMADEUS_CLIENT_ID', "").strip()
client_secret = os.getenv('AMADEUS_CLIENT_SECRET', "").strip()
amadeus = Client(client_id=client_id, client_secret=client_secret, hostname='test')

if 'selected_hotel_id' not in st.session_state:
    st.session_state.selected_hotel_id = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = True 

# --- SIDEBAR: SEARCH & HOTEL LIST (800px maintained) ---
with st.sidebar:
    st.markdown("### 🔍 Search Hotels")
    search_query = st.text_input("filter_search", placeholder="Type hotel name...", label_visibility="collapsed")
    
    st.divider()
    
    st.subheader("Monitored Properties")
    all_hotels = filter_leads.get_monitored_leads(amadeus)
    
    filtered = [h for h in all_hotels if search_query.lower() in h['hotel']['name'].lower()]
    
    with st.container(height=800, border=False):
        if filtered:
            for hotel in filtered:
                h_name = hotel['hotel']['name']
                h_id = hotel['hotel']['hotelId']
                
                is_selected = st.session_state.selected_hotel_id == h_id
                if st.button(h_name, key=f"btn_{h_id}", use_container_width=True, 
                             type="primary" if is_selected else "secondary"):
                    st.session_state.selected_hotel_id = h_id
                    st.session_state.current_hotel_name = h_name
                    st.rerun()
        else:
            st.write("No hotels found.")

    st.divider()

    st.markdown(f"#### 👤 {st.session_state.get('user_email', 'Georgia Whalen')}")
    if st.button("🚪 Log Off", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.rerun()

# --- MAIN DASHBOARD: INVENTORY INTELLIGENCE ---
if not st.session_state.logged_in:
    st.warning("Please log in to continue.")
    if st.button("Log In"): 
        st.session_state.logged_in = True
        st.rerun()
    st.stop()

if st.session_state.selected_hotel_id:
    st.header(st.session_state.current_hotel_name)
    
    df = filter_leads.get_60_day_insight(amadeus, st.session_state.selected_hotel_id)
    
    if not df.empty:
        room_types = list(df["Unit Type"].unique())
        tabs = st.tabs(room_types)

        for i, tab in enumerate(tabs):
            with tab:
                current_room = room_types[i]
                room_df = df[df["Unit Type"] == current_room]

                # 1. VISUAL INTELLIGENCE (Fixed with Unique Keys)
                c1, c2 = st.columns(2)
                with c1:
                    fig_p = px.line(room_df, x="Date", y="Rate_Float", 
                                   title="Price Trend ($)", 
                                   color_discrete_sequence=["#FFA500"])
                    # Added unique key using room name and index
                    st.plotly_chart(fig_p, use_container_width=True, key=f"price_chart_{current_room}_{i}")
                
                with c2:
                    fig_i = px.bar(room_df, x="Date", y="Rooms Available", 
                                  title="Units Available",
                                  color_discrete_sequence=["#0078D4"])
                    fig_i.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Target: 10")
                    # Added unique key
                    st.plotly_chart(fig_i, use_container_width=True, key=f"inv_chart_{current_room}_{i}")

                # 2. RAW INVENTORY DATA (Fixed with Unique Key)
                st.subheader(f"10-Unit Availability Check: {current_room}")
                st.dataframe(
                    room_df[["Date", "Availability Status", "Rooms Available", "Rate"]],
                    column_config={
                        "Rooms Available": st.column_config.NumberColumn("Units Left", format="%d 🏨"),
                        "Availability Status": st.column_config.TextColumn("Target Match"),
                    },
                    use_container_width=True, 
                    hide_index=True,
                    key=f"data_table_{current_room}_{i}"
                )
else:
    st.info("👈 Search and select a property to view 10-unit availability.")