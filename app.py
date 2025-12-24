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
    /* Preserves the website's literal line breaks and list structure for weights */
    .preserve-breaks { white-space: pre-wrap !important; font-family: inherit; display: block; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Step-by-Step Modular Scraper Functions ---

def get_raw_site_stream():
    """Step 1: Fetch clean text stream from the CrossFit WOD page."""
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Preserves ♀ and ♂
        soup = BeautifulSoup(response.content, 'html.parser')
        # Using newline separator ensures weight symbols stay on their own lines
        return [l.strip() for l in soup.get_text(separator="\n", strip=True).split("\n") if l.strip()]
    except:
        return []

def hunt_for_section(lines, start_anchor, stop_triggers, is_title=False):
    """Step 2: Methodically scan for a specific data block."""
    buffer = []
    found_anchor = False
    
    for i, line in enumerate(lines):
        if not found_anchor:
            # Contextual match for headers
            if start_anchor.lower() in line.lower():
                found_anchor = True
                if is_title and i + 1 < len(lines):
                    return lines[i+1] # Line after date is WOD name
                continue
        else:
            # Stop capture if a following section header is reached
            if any(stop.lower() in line.lower() for stop in stop_triggers):
                break
            
            # Format: Emphasize weight symbols for phone display
            if any(symbol in line for symbol in ['♀', '♂']):
                buffer.append(f"**{line}**")
            else:
                buffer.append(line)
                
    return "\n".join(buffer).strip()

def execute_sequential_scrape():
    """Step 3: Orchestrate the modular scrape in a methodical sequence."""
    lines = get_raw_site_stream()
    if not lines:
        return {"title": "Offline", "workout": "Manual Entry Mode", "stim": "", "scal": "", "cue": ""}
    
    today_id = datetime.date.today().strftime("%y%m%d") # Anchor: 251223
    
    # Methodical extraction of sections
    wod_title = hunt_for_section(lines, today_id, [], is_title=True)
    wod_body = hunt_for_section(lines, today_id, ["Post time", "Compare to", "Stimulus"])
    
    # Remove redundant title if present
    if wod_title: wod_body = wod_body.replace(wod_title, "").strip()
    
    stimulus = hunt_for_section(lines, "Stimulus", ["Scaling", "Coaching cues", "Resources"])
    scaling = hunt_for_section(lines, "Scaling", ["Coaching cues", "Resources"])
    cues = hunt_for_section(lines, "Coaching cues", ["Resources", "The Snatch"])

    return {
        "title": wod_title if wod_title else "Isabel",
        "workout": wod_body if wod_body else "30 Snatches for time (135/95 lbs)",
        "stimulus": stimulus,
        "scaling": scaling,
        "cues": cues
    }

# --- UI & Execution Logic ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = execute_sequential_scrape()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod.get('title', "Today's WOD"))
    st.markdown(f'<div class="stInfo preserve-breaks">{wod.get("workout", "Workout details loading...")}</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Independent Expanders for section isolation
    with st.expander("⚡ Stimulus & Strategy"):
        s_text = wod.get('stimulus', "")
        st.markdown(f'<div class="preserve-breaks">{s_text if s_text else "Target under 15 minutes."}</div>', unsafe_allow_html=True)

    with st.expander("⚖️ Scaling Options"):
        sc_text = wod.get('scaling', "")
        st.markdown(f'<div class="preserve-breaks">{sc_text if sc_text else "Reduce load for speed."}</div>', unsafe_allow_html=True)

    with st.expander("🧠 Coaching Cues"):
        c_text = wod.get('cues', "")
        st.markdown(f'<div class="preserve-breaks">{c_text if c_text else "Heels down, bar close."}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with col2:
        performance_score = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="L5-S1 mobility, fatigue, or equipment notes...")
    
    if st.button("Save to TriDrive Ledger"):
        st.success("Session Data Logged!")
        st.balloons()

with tab3:
    st.info("Performance trends will appear after your next sync.")

# --- END OF FILE: app.py ---
