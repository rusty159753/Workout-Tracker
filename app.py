import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. INDUSTRIAL UI ---
st.set_page_config(page_title="TriDrive MVP", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    /* EFFICACY FIX: Preserves line breaks for weights and symbols */
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 10px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- 2. RESILIENT COMMUNICATION SCRAPER ---
def scrape_with_retry():
    url = "https://www.crossfit.com/wod"
    # Browser-mimicry headers to prevent site blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        # Step 1: Open Communication
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Critical for symbol rendering
        
        # Step 2: Validate Data Structure
        soup = BeautifulSoup(response.content, 'html.parser')
        article = soup.find('article') or soup.find('div', class_='content')
        if not article: return None

        # Step 3: Literal Line Extraction
        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        today_code = datetime.date.today().strftime("%y%m%d")
        data = {"title": "Isabel", "workout": [], "stim": [], "scal": [], "cue": []}
        mode = "WAITING"

        for i, line in enumerate(lines):
            # Anchor Detection
            if today_code in line:
                mode = "WORKOUT"
                if i + 1 < len(lines): data["title"] = lines[i+1]
                continue
            if "Stimulus" in line: mode = "STIM"
            elif "Scaling" in line: mode = "SCAL"
            elif "Coaching cues" in line: mode = "CUE"
            
            # Stop Conditions
            if any(stop in line for stop in ["Resources", "View results"]): break

            # Contextual Capture
            if mode == "WORKOUT":
                if line != data["title"] and today_code not in line:
                    if any(s in line for s in ['♀', '♂']):
                        data["workout"].append(f"**{line}**")
                    else:
                        data["workout"].append(line)
            elif mode in ["STIM", "SCAL", "CUE"]:
                if not any(h in line for h in ["Stimulus", "Scaling", "Coaching cues"]):
                    data[mode.lower()].append(line)

        return {
            "title": data["title"],
            "workout": "\n".join(data["workout"]),
            "stimulus": "\n\n".join(data["stim"]), # Preserves paragraph spacing
            "scaling": "\n\n".join(data["scal"]),
            "cues": "\n".join(data["cue"])
        }
    except:
        return None

# --- 3. UI & PERSISTENCE ---
st.title("TRI⚡DRIVE")
st.caption("Owner Audit: Communication-Resilient Build")

# Manual Override in Sidebar
if st.sidebar.button("Force Scrape Refresh"):
    st.session_state.wod_data = scrape_with_retry()

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_with_retry()

wod = st.session_state.wod_data

if wod:
    tab1, tab2, tab3 = st.tabs(["🔥 WOD", "📊 Log", "📈 Analytics"])
    with tab1:
        st.subheader(wod['title'])
        st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
        
        if wod['stimulus']:
            with st.expander("⚡ Stimulus & Strategy"):
                st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)
        if wod['scaling']:
            with st.expander("⚖️ Scaling"):
                st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)
else:
    st.error("Communication issue with CrossFit.com. Check connection or hit 'Refresh'.")

# --- END OF FILE: app.py ---
