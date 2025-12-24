import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config & High-Fidelity Styling ---
st.set_page_config(page_title="TriDrive Performance", page_icon="⚡", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 10px; font-size: 1.15rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 10px; border: 1px solid #3e3e4e; }
    .preserve-breaks { white-space: pre-wrap !important; font-family: inherit; display: block; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Step-by-Step Scraper Functions ---

def get_full_page_lines():
    """Step 1: Get the raw, clean lines of text from the whole page."""
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        return [line.strip() for line in soup.get_text(separator="\n", strip=True).split("\n") if line.strip()]
    except:
        return []

def extract_section(lines, start_key, end_keys, title_mode=False):
    """Utility to pull text between two defined markers."""
    capture = []
    found_start = False
    today_code = datetime.date.today().strftime("%y%m%d")
    
    for i, line in enumerate(lines):
        if not found_start:
            # Check for the start marker (Date Code or Section Header)
            if start_key in line:
                found_start = True
                if title_mode and i + 1 < len(lines):
                    return lines[i+1] # Special mode just to get the WOD Title
                continue
        else:
            # Stop if we hit any of the end markers
            if any(end in line for end in end_keys):
                break
            # Formatting: Bold the weight lines (♀/♂)
            if any(c in line for c in ['♀', '♂']):
                capture.append(f"**{line}**")
            else:
                capture.append(line)
    return "\n".join(capture)

def scrape_step_by_step():
    lines = get_full_page_lines()
    if not lines:
        return {"title": "Offline", "workout": "Manual Entry Mode", "stimulus": "", "scaling": "", "cues": ""}
    
    today_code = datetime.date.today().strftime("%y%m%d")
    
    # Step 2: Identify Title
    title = extract_section(lines, today_code, [], title_mode=True)
    
    # Step 3: Extract Workout (Anchor -> Post time)
    workout = extract_section(lines, today_code, ["Post time to comments", "Compare to"])
    workout = workout.replace(title, "").strip() # Clean redundancy
    
    # Step 4: Extract Stimulus (Stimulus -> Scaling)
    stimulus = extract_section(lines, "Stimulus", ["Scaling", "Coaching cues", "Resources"])
    
    # Step 5: Extract Scaling (Scaling -> Coaching cues)
    scaling = extract_section(lines, "Scaling", ["Coaching cues", "Resources"])
    
    # Step 6: Extract Cues (Coaching cues -> Resources)
    cues = extract_section(lines, "Coaching cues", ["Resources", "The Snatch"])

    return {
        "title": title if title else "Today's WOD",
        "workout": workout if workout else "Isabel: 30 Snatches (135/95 lb)",
        "stimulus": stimulus,
        "scaling": scaling,
        "cues": cues
    }

# --- Persistence ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UI Setup ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_step_by_step()

wod = st.session_state.wod_data

# Tab 1: The WOD
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod.get('title', "Today's WOD"))
    st.markdown(f'<div class="stInfo preserve-breaks">{wod.get("workout", "No workout text found.")}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Each section is now its own isolated UI component
    with st.expander("⚡ Stimulus & Strategy"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("stimulus", "Not found.")}</div>', unsafe_allow_html=True)

    with st.expander("⚖️ Scaling Options"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("scaling", "Not found.")}</div>', unsafe_allow_html=True)

    with st.expander("🧠 Coaching Cues"):
        st.markdown(f'<div class="preserve-breaks">{wod.get("cues", "Not found.")}</div>', unsafe_allow_html=True)

# Tab 2: Logging (Standardized to prevent errors)
with tab2:
    st.subheader("Performance Log")
    c1, c2 = st.columns(2)
    with c1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with c2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="L
                    
