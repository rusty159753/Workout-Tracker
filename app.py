import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 1. CONFIG MUST BE FIRST ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")

# --- CUSTOM CSS: FORCE WHITE TEXT ON BLUE ---
st.markdown("""
<style>
/* Target the st.info box */
[data-testid="stNotification"] {
    background-color: #172b4d; /* Deep CrossFit Blue */
    border: 1px solid #3b5e8c;
    color: #ffffff !important; /* Force White Text */
}
[data-testid="stNotification"] p {
    color: #ffffff !important; /* Force White Paragraphs */
    font-size: 16px;
    line-height: 1.6;
}
[data-testid="stMarkdownContainer"] ul {
    color: #ffffff !important; /* Force White Lists */
}
</style>
""", unsafe_allow_html=True)

# --- DEBUG: Hard Reset Button ---
with st.sidebar:
    st.header("🔧 Diagnostics")
    if st.button("⚠️ Hard Reset App", type="primary"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# --- 2. ENVIRONMENT CHECK ---
try:
    import cloudscraper
    import gspread
    from google.oauth2.service_account import Credentials
    READY_TO_SYNC = True
    st.sidebar.success("Dependencies: OK")
except ImportError:
    READY_TO_SYNC = False
    st.sidebar.error("Dependencies: Missing")

# --- 3. SESSION STATE ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'VIEWER'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}

# --- 4. THE JANITOR (Version 5.0: Paragraphs & Lists) ---
def sanitize_text(text):
    if not text: return ""
    
    # 1. Encoding Fixes (Smart Quotes)
    replacements = {
        "": "'", "â": "'", "’": "'", "‘": "'", 
        "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # 2. Soup Cleaning with Structural Awareness
    soup = BeautifulSoup(text, "html.parser")
    
    # Force paragraphs and divs to have double newlines for spacing
    for tag in soup.find_all(['p', 'div', 'li']):
        tag.insert_after("\n\n")
        
    # Force breaks to be single newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")
        
    text = soup.get_text(separator="", strip=True) 
    
    # 3. Unicode Normalization
    text = unicodedata.normalize("NFKD", text)
    
    # 4. Clean up massive gaps (more than 2 newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

# --- 5. THE MAPPER ---
def parse_workout_data(wod_data):
    if isinstance(wod_data, str):
        full_blob = sanitize_text(wod_data)
        title = "Workout of the Day"
    else:
        raw_main = wod_data.get('main_text', '')
        raw_stim = wod_data.get('stimulus', '')
        full_blob = sanitize_text(raw_main + "\n\n" + raw_stim)
        title = wod_data.get('title', 'Workout of the Day')

    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE)
tate.get('current_wod', {})
        
        if not wod:
            st.error("No WOD loaded.")
            if st.button("Back"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
        else:
            st.success(f"Imported: {wod.get('title', 'Unknown')}")
            
            formatted_rx = wod.get('workout', 'No Data').replace("\n", "  \n")
            st.markdown(f"**Rx Workout:** \n{formatted_rx}")
            
            st.warning("⚠️ Phase 3 Construction Zone")
            
            if st.button("⬅️ Back to Viewer"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
tate.get('current_wod', {})
        
        if not wod:
            st.error("No WOD loaded.")
            if st.button("Back"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
        else:
            st.success(f"Imported: {wod.get('title', 'Unknown')}")
            
            formatted_rx = wod.get('workout', 'No Data').replace("\n", "  \n")
            st.markdown(f"**Rx Workout:** \n{formatted_rx}")
            
            st.warning("⚠️ Phase 3 Construction Zone")
            
            if st.button("⬅️ Back to Viewer"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
