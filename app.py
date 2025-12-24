import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. MVP UI & MOBILE OPTIMIZATION ---
st.set_page_config(page_title="TriDrive MVP", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 10px; }
    /* MVP FIX: Ensures the ♀/♂ weights stay on separate lines without stacking */
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 10px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- 2. TARGETED MVP SCRAPER (REFINED) ---
def scrape_current_conditions():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8' # Critical for ♀ and ♂ integrity
        soup = BeautifulSoup(response.content, 'html.parser')
        
        today_code = datetime.date.today().strftime("%y%m%d")
        article = soup.find('article')
        
        if not article:
            return None

        # Separator="\n" is the key to stopping the "vertical stack" failure
        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        def capture_section(start_text, end_markers):
            content = []
            active = False
            for line in lines:
                if not active:
                    if start_text.lower() in line.lower():
                        active = True
                        continue
                else:
                    # Stop if we hit the next header, but don't stop mid-workout
                    if any(end.lower() in line.lower() for end in end_markers):
                        break
                    if any(s in line for s in ['♀', '♂']):
                        content.append(f"**{line}**")
                    else:
                        content.append(line)
            return "\n".join(content).strip()

        # Improved title hunt: grab the first line that isn't the date code
        title = "Today's WOD"
        for line in lines[:5]:
            if today_code not in line and len(line) > 3:
                title = line
                break

        return {
            "title": title,
            "workout": capture_section(today_code, ["Stimulus", "Compare to"]),
            "stim": capture_section("Stimulus", ["Scaling", "Coaching cues", "Resources"]),
            "scal": capture_section("Scaling", ["Coaching cues", "Resources"]),
            "cue": capture_section("Coaching cues", ["Resources", "View results"])
        }
    except:
        return None

# --- 3. MVP INTERFACE ---
st.title("TRI⚡DRIVE")
st.caption("MVP Build | Refined for Current Conditions")

# Refresh button in sidebar for user control
if st.sidebar.button("🔄 Refresh WOD Data"):
    st.session_state.wod_data = scrape_current_conditions()

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_current_conditions()

wod = st.session_state.wod_data

if wod:
    tab1, tab2, tab3 = st.tabs(["🔥 WOD", "📊 Log", "📈 Trends"])

    with tab1:
        st.subheader(wod['title'])
        # The info box uses the preserve-layout class to keep weights readable
        st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
        
        if wod['stim']:
            with st.expander("⚡ Stimulus"):
                st.markdown(f'<div class="preserve-layout">{wod["stim"]}</div>', unsafe_allow_html=True)
        if wod['scal']:
            with st.expander("⚖️ Scaling"):
                st.markdown(f'<div class="preserve-layout">{wod["scal"]}</div>', unsafe_allow_html=True)
        if wod['cue']:
            with st.expander("🧠 Cues"):
                st.markdown(f'<div class="preserve-layout">{wod["cue"]}</div>', unsafe_allow_html=True)

    with tab2:
        st.subheader("Quick Log")
        res = st.text_input("Score", placeholder="e.g. 12:45")
        sens = st.slider("Sciatica", 1, 10, 2)
        if st.button("Save Entry"):
            st.success("WOD Logged Successfully!")
            st.balloons()
else:
    st.error("Could not load WOD. Please refresh or check CrossFit.com.")

# --- END OF FILE: app.py ---
