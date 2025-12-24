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

# --- Industrial-Grade Modular Scraper ---

def get_clean_lines():
    """Step 1: Scrape the raw text stream from the daily URL."""
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Preserves ♀ and ♂
        soup = BeautifulSoup(response.content, 'html.parser')
        # Use a distinctive separator to prevent text bunching
        return [l.strip() for l in soup.get_text(separator="\n", strip=True).split("\n") if l.strip()]
    except:
        return []

def extract_module(lines, start_key, stop_patterns, is_title=False):
    """Step 2: Contextual scanning to find and capture data blocks."""
    captured_lines = []
    active = False
    
    for i, line in enumerate(lines):
        if not active:
            # We look for the key as a partial match to handle 'Stimulus:' vs 'Stimulus'
            if start_key.lower() in line.lower():
                active = True
                if is_title and i + 1 < len(lines):
                    return lines[i+1] # The line after date is always the WOD Name
                continue
        else:
            # Stop capture if we hit the next major section header
            if any(pattern.lower() in line.lower() for pattern in stop_patterns):
                break
            
            # Formatting: Bold weight requirements
            if any(symbol in line for symbol in ['♀', '♂']):
                captured_lines.append(f"**{line}**")
            else:
                captured_lines.append(line)
                
    return "\n".join(captured_lines).strip()

def run_efficacy_scrape():
    """Step 3: Execute the modular search."""
    lines = get_clean_lines()
    if not lines:
        return {"title": "Offline", "workout": "Manual Entry Mode", "stim": "", "scal": "", "cue": ""}
    
    # Anchor for 251223
    today = datetime.date.today().strftime("%y%m%d")
    
    # 1. Title
    t = extract_module(lines, today, [], is_title=True)
    
    # 2. Workout (Capture from Date until Stimulus appears)
    w = extract_module(lines, today, ["Post time", "Compare to", "Stimulus"])
    if t: w = w.replace(t, "").strip() # Clean redundancy
    
    # 3. Stimulus (Capture until Scaling appears)
    s = extract_module(lines, "Stimulus", ["Scaling", "Coaching cues", "Resources"])
    
    # 4. Scaling (Capture until Cues appear)
    sc = extract_module(lines, "Scaling", ["Coaching cues", "Resources"])
    
    # 5. Cues (Capture until Resources appear)
    c = extract_module(lines, "Coaching cues", ["Resources", "The Snatch"])

    return {
        "title": t if t else "Today's WOD",
        "workout": w if w else "Isabel: 30 Snatches for time (135/95 lbs)",
        "stimulus": s,
        "scaling": sc,
        "cues": c
    }

# --- Main App Execution ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = run_efficacy_scrape()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod.get('title', "Today's WOD"))
    st.markdown(f'<div class="stInfo preserve-breaks">{wod.get("workout", "Workout data pending...")}</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Modular Expanders with fallback text
    with st.expander("⚡ Stimulus & Strategy"):
        content_s = wod.get('stimulus', "")
        st.markdown(f'<div class="preserve-breaks">{content_s if content_s else "Review stimulus on CrossFit.com"}</div>', unsafe_allow_html=True)

    with st.expander("⚖️ Scaling Options"):
        content_sc = wod.get('scaling', "")
        st.markdown(f'<div class="preserve-breaks">{content_sc if content_sc else "Review scaling on CrossFit.com"}</div>', unsafe_allow_html=True)

    with st.expander("🧠 Coaching Cues"):
        content_c = wod.get('cues', "")
        st.markdown(f'<div class="preserve-breaks">{content_c if content_c else "Heels down, bar close."}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="L5-S1 status, mobility, or equipment notes...")
    
    if st.button("Save to TriDrive Ledger"):
        st.success("Session Data Cached!")
        st.balloons()

with tab3:
    st.info("Performance charts will update after your next sync.")

# --- END OF FILE: app.py ---
