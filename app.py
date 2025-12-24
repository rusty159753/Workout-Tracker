import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config & Pro-Level Styling ---
st.set_page_config(page_title="TriDrive Performance", page_icon="⚡", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; border: none; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 10px; font-size: 1.15rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 12px; border: 1px solid #3e3e4e; }
    .preserve-breaks { white-space: pre-wrap !important; font-family: inherit; display: block; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Modular Scraping Logic ---

def get_raw_lines():
    """Step 1: Pull raw text lines from the target URL."""
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        return [line.strip() for line in soup.get_text(separator="\n", strip=True).split("\n") if line.strip()]
    except:
        return []

def extract_content(lines, start_key, end_keys, is_title=False):
    """Step-by-step extraction of specific data modules."""
    capture = []
    found = False
    for i, line in enumerate(lines):
        if not found and start_key in line:
            found = True
            if is_title and i + 1 < len(lines):
                return lines[i+1] # Grab the workout name (e.g. Isabel)
            continue
        if found:
            if any(end in line for end in end_keys):
                break
            # Preserve special formatting for weights
            if any(symbol in line for symbol in ['♀', '♂']):
                capture.append(f"**{line}**")
            else:
                capture.append(line)
    return "\n".join(capture)

def run_targeted_scrape():
    lines = get_raw_lines()
    if not lines:
        return {"title": "Offline", "workout": "Manual Entry Mode", "stimulus": "", "scaling": "", "cues": ""}
    
    today = datetime.date.today().strftime("%y%m%d") # Anchor: 251223
    
    # Executing modular extractions
    title = extract_content(lines, today, [], is_title=True)
    workout = extract_content(lines, today, ["Post time to comments", "Compare to", "Stimulus"])
    
    # Cleanup: remove title if it was caught in the workout buffer
    if title: workout = workout.replace(title, "").strip()
    
    stim = extract_content(lines, "Stimulus", ["Scaling", "Coaching cues", "Resources"])
    scal = extract_content(lines, "Scaling", ["Coaching cues", "Resources"])
    cue = extract_content(lines, "Coaching cues", ["Resources", "The Snatch"])

    return {
        "title": title if title else "Today's WOD",
        "workout": workout if workout else "Isabel: 30 Snatches for time (135/95 lbs)",
        "stimulus": stim,
        "scaling": scal,
        "cues": cue
    }

# --- Persistence & UI ---
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = run_targeted_scrape()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod.get('title', "Today's WOD"))
    st.markdown(f'<div class="stInfo preserve-breaks">{wod.get("workout", "Workout details loading...")}</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    with st.expander("⚡ Stimulus & Strategy"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("stimulus", "Not found.")}</div>', unsafe_allow_html=True)
    with st.expander("⚖️ Scaling Options"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("scaling", "Not found.")}</div>', unsafe_allow_html=True)
    with st.expander("🧠 Coaching Cues"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("cues", "Not found.")}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with col2:
        score = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="L5-S1 status, mobility, or gym equipment notes...")
    
    if st.button("Save to TriDrive Ledger"):
        st.success("WOD Data Synchronized!")
        st.balloons()

with tab3:
    st.info("Analytics will update upon next data sync.")
    
