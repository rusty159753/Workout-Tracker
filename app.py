import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import re
from streamlit_gsheets import GSheetsConnection

# --- Page Config ---
st.set_page_config(page_title="TriDrive Performance", page_icon="🚴‍♂️", layout="centered")

# --- Custom Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stTextInput>div>div>input { background-color: #262730; color: white; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Industrial-Grade Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Target the YYMMDD anchor
        today_code = datetime.date.today().strftime("%y%m%d")
        
        # Get every text element to bypass hidden/dynamic containers
        # CrossFit posts often wrap the real data in a generic <article>
        main_content = soup.find('article')
        if not main_content:
            return {"title": "Error", "workout": "Content container not reachable.", "scaling": "", "score_type": "Other"}

        raw_text = main_content.get_text(separator="|||", strip=True)
        lines = [line.strip() for line in raw_text.split("|||") if line.strip()]
        
        # State Machine for Segmenting the Daily Post
        wod_lines = []
        scaling_lines = []
        capture_mode = "SEEK_DATE"
        title = "Today's WOD"

        for i, line in enumerate(lines):
            # 1. Trigger: Find the Date Code
            if today_code in line:
                capture_mode = "WOD"
                # Logic: The line immediately following the date is the Title
                if i + 1 < len(lines):
                    potential_title = lines[i+1]
                    if "Workout of the Day" not in potential_title:
                        title = potential_title
                continue
            
            # 2. Transition: Detect Scaling/Strategy Headers
            if "Scaling" in line:
                capture_mode = "SCALING"
                continue
            
            # 3. Stop: Detect End-of-Post markers
            if any(stop in line for stop in ["Post time", "View results", "Comments"]):
                break

            # 4. Collection Logic
            if capture_mode == "WOD":
                # We include the 'Workout of the Day' text only if it's the core content
                if "Workout of the Day" not in line and line != title:
                    wod_lines.append(line)
            elif capture_mode == "SCALING":
                scaling_lines.append(line)

        # Assemble cleaned output
        workout_body = "\n\n".join(wod_lines) if wod_lines else "Isabel: 30 Snatches for time (135/95 lbs)"
        
        return {
            "title": title,
            "workout": workout_body,
            "scaling": "\n\n".join(scaling_lines) if scaling_lines else "Scale for Isabel stimulus (under 15 min).",
            "score_type": "AMRAP" if "AMRAP" in workout_body.upper() else "For Time"
        }

    except Exception as e:
        return {"title": "Manual Entry Mode", "workout": f"Technical Issue: {e}", "scaling": "", "score_type": "Other"}

# --- Data Handshake ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data):
    try:
        existing = conn.read(ttl=0)
        new_row = pd.DataFrame([data])
        updated = pd.concat([existing, new_row], ignore_index=True) if not existing.empty else new_row
        conn.update(data=updated)
        return True
    except:
        return False

# --- App Structure ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_crossfit_wod()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod['title'])
    st.info(wod['workout'])
    st.write("### YMCA Scaling & Adaptations")
    st.text_area("YMCA Safety Notes:", value=wod['scaling'], height=300)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        sciatica = st.slider("Sciatica Sensitivity", 1, 10, 2)
        weight = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        notes = st.text_area("Gym Notes", placeholder="Back felt...")
    
    if st.button("Save to TriDrive Ledger"):
        entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "WOD_Name": wod['title'], "Result": res, "Weight": weight, "Sciatica_Score": sciatica, "Notes": notes}
        if save_entry(entry):
            st.success("WOD Logged!")
            st.balloons()

with tab3:
    try:
        history = conn.read(ttl=0)
        if not history.empty:
            history['Date'] = pd.to_datetime(history['Date'])
            st.line_chart(history.set_index('Date')[['Sciatica_Score', 'Weight']])
            st.dataframe(history.tail(5), use_container_width=True)
    except:
        st.info("Awaiting initial data entry.")
            
