import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. UI ARCHITECTURE & MOBILE OVERRIDES ---
st.set_page_config(page_title="TriDrive Performance", page_icon="⚡", layout="centered")

# Custom CSS to mirror the website's literal layout on mobile devices
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; border: none; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 10px; font-size: 1.15rem; line-height: 1.7; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 12px; border: 1px solid #3e3e4e; }
    /* Fixes vertical stacking of weights and units */
    .preserve-layout { white-space: pre-wrap !important; word-wrap: break-word; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- 2. THE STATE MACHINE SCRAPER ---
def industrial_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        # Prevents weight symbols from breaking during the request
        response.encoding = 'utf-8' 
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Anchor: Today's date code (YYMMDD)
        today_code = datetime.date.today().strftime("%y%m%d")
        
        # Target the main container to avoid header/footer noise
        article = soup.find('article')
        if not article:
            return {"title": "Rest Day", "workout": "Manual Log Required", "stim": "", "scal": "", "cue": ""}

        # Capture lines while preserving original line break structure
        raw_lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        # Capture buffers
        segments = {"WORKOUT": [], "STIM": [], "SCAL": [], "CUE": []}
        mode = "WAITING"
        title = "Today's WOD"

        for i, line in enumerate(raw_lines):
            # Transition 1: Date code triggers the start
            if today_code in line:
                mode = "WORKOUT"
                if i + 1 < len(raw_lines): title = raw_lines[i+1]
                continue
            
            # Transition 2: Switch modes based on section headers
            if "Stimulus" in line: mode = "STIM"
            elif "Scaling" in line: mode = "SCAL"
            elif "Coaching cues" in line: mode = "CUE"
            elif "Post time to comments" in line: mode = "END_WOD"
            elif any(stop in line for stop in ["Resources", "View results"]): break

            # Capture logic
            if mode == "WORKOUT" and line != title:
                # Force bolding on weight requirements for better phone visibility
                if any(symbol in line for symbol in ['♀', '♂']):
                    segments["WORKOUT"].append(f"**{line}**")
                else:
                    segments["WORKOUT"].append(line)
            elif mode in ["STIM", "SCAL", "CUE"]:
                # Add text to current segment, excluding the header itself
                if not any(h in line for h in ["Stimulus", "Scaling", "Coaching cues"]):
                    segments[mode].append(line)

        return {
            "title": title,
            "workout": "\n".join(segments["WORKOUT"]),
            "stimulus": "\n".join(segments["STIM"]),
            "scaling": "\n".join(segments["SCAL"]),
            "cues": "\n".join(segments["CUE"])
        }
    except Exception as e:
        return {"title": "Connection Error", "workout": f"Technical Issue: {e}", "stim": "", "scal": "", "cue": ""}

# --- 3. PERSISTENCE LAYER ---
conn = st.connection("gsheets", type=GSheetsConnection)

def log_session(data):
    try:
        # ttl=0 forces a fresh read from the sheet before updating
        existing = conn.read(ttl=0)
        new_row = pd.DataFrame([data])
        updated = pd.concat([existing, new_row], ignore_index=True) if not existing.empty else new_row
        conn.update(data=updated)
        return True
    except:
        return False

# --- 4. UI RENDER ENGINE ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = industrial_scrape()

wod = st.session_state.wod_data
tabs = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tabs[0]:
    st.subheader(wod["title"])
    # Uses the 'preserve-layout' class to mirror the CrossFit website format
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    if wod["stimulus"]:
        with st.expander("⚡ Stimulus & Strategy"):
            st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)

    if wod["scaling"]:
        with st.expander("⚖️ Scaling Options"):
            st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)

    if wod["cues"]:
        with st.expander("🧠 Coaching Cues"):
            st.markdown(f'<div class="preserve-layout">{wod["cues"]}</div>', unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        sens = st.slider("Sciatica Sensitivity", 1, 10, 2)
        weight = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        notes = st.text_area("Gym Notes", placeholder="L5-S1 feedback...")
    
    if st.button("Log to Ledger"):
        log_data = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "WOD": wod['title'],
            "Result": res,
            "BW": weight,
            "Sciatica": sens,
            "Notes": notes
        }
        if log_session(log_data):
            st.success("Entry Logged!")
            st.balloons()

with tabs[2]:
    st.info("Performance charts will update after your next successful log.")

# --- END OF FILE: app.py ---
