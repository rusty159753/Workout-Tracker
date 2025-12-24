import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. INDUSTRIAL MOBILE UI ---
st.set_page_config(page_title="TriDrive MVP", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 10px; }
    /* EFFICACY FIX: Preserves ♀/♂ horizontal alignment and paragraph spacing */
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 10px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- 2. FINAL BOUNDARY-LOCKED SCRAPER ---
def run_final_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.encoding = 'utf-8' # Preserves ♀ and ♂ integrity
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Target the core article to ignore navigation sidebars
        article = soup.find('article') or soup.find('div', class_='content')
        if not article: return None

        # Maintain literal vertical line structure using newline separators
        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        today_code = datetime.date.today().strftime("%y%m%d")
        data = {"title": "Isabel", "workout": [], "stimulus": [], "scaling": [], "cues": []}
        mode = "WAITING"

        for i, line in enumerate(lines):
            # Section Anchor Identification
            if today_code in line:
                mode = "WORKOUT"
                if i + 1 < len(lines): data["title"] = lines[i+1]
                continue
            if "Stimulus" in line: mode = "STIMULUS"
            elif "Scaling" in line: mode = "SCALING"
            elif "Coaching cues" in line: mode = "CUES"
            
            # Termination Guard: Stop if we hit global footer resources
            if any(stop in line for stop in ["Resources", "View results"]): break

            # Step-by-Step Contextual Capture
            if mode == "WORKOUT":
                # Exclude the Date and Title from the movements box
                if line != data["title"] and today_code not in line:
                    if any(s in line for s in ['♀', '♂']):
                        data["workout"].append(f"**{line}**")
                    else:
                        data["workout"].append(line)
            elif mode in ["STIMULUS", "SCALING", "CUES"]:
                # Capture everything between the headers
                if not any(h in line for h in ["Stimulus", "Scaling", "Coaching cues"]):
                    data[mode.lower()].append(line)

        # Formatting: Double-newline for long-form text blocks
        return {
            "title": data["title"],
            "workout": "\n".join(data["workout"]),
            "stimulus": "\n\n".join(data["stimulus"]),
            "scaling": "\n\n".join(data["scaling"]),
            "cues": "\n".join(data["cues"])
        }
    except:
        return None

# --- 3. PERSISTENCE & UI ---
conn = st.connection("gsheets", type=GSheetsConnection)

def log_to_ledger(data):
    try:
        existing = conn.read(ttl=0)
        updated = pd.concat([existing, pd.DataFrame([data])], ignore_index=True) if not existing.empty else pd.DataFrame([data])
        conn.update(data=updated)
        return True
    except: return False

# --- 4. INTERFACE ---
st.title("TRI⚡DRIVE")
st.caption("Industrial MVP Build | 2025.12.23")

if st.session_state.wod_data is None:
    st.session_state.wod_data = run_final_scrape()

wod = st.session_state.wod_data

if wod:
    tab1, tab2, tab3 = st.tabs(["🔥 WOD", "📊 Log", "📈 Trends"])

    with tab1:
        st.subheader(wod.get('title', "Isabel"))
        # Preserves horizontal alignment for weights
        st.markdown(f'<div class="stInfo preserve-layout">{wod.get("workout", "Details missing.")}</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        if wod.get('stimulus'):
            with st.expander("⚡ Stimulus & Strategy"):
                st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)

        if wod.get('scaling'):
            with st.expander("⚖️ Scaling"):
                st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)

        if wod.get('cues'):
            with st.expander("🧠 Cues"):
                st.markdown(f'<div class="preserve-layout">{wod["cues"]}</div>', unsafe_allow_html=True)
    
    with tab2:
        st.subheader("Performance Log")
        res = st.text_input("Score", placeholder="e.g. 12:45")
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        if st.button("Commit to Ledger"):
            if log_to_ledger({"Date": datetime.date.today().strftime("%Y-%m-%d"), "WOD": wod['title'], "Result": res, "Back": s_score}):
                st.success("Entry Synchronized!")
                st.balloons()
else:
    st.error("Site connectivity issue. Check CrossFit.com directly.")

# --- END OF FILE: app.py ---
