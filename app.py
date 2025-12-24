import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- ENVIRONMENT CHECK ---
try:
    import cloudscraper
    import gspread
    from google.oauth2.service_account import Credentials
    READY_TO_SYNC = True
except ImportError:
    READY_TO_SYNC = False

# --- SESSION STATE INITIALIZATION (The "Brain") ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'VIEWER' # Default to Read-Only
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}

# --- STEP 1: THE JANITOR ---
def sanitize_text(text):
    if not text: return ""
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    text = unicodedata.normalize("NFKD", text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- STEP 2: THE MAPPER ---
def parse_workout_data(wod_data):
    raw_main = wod_data.get('main_text', '')
    raw_stim = wod_data.get('stimulus', '')
    full_blob = sanitize_text(raw_main + " " + raw_stim)

    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE)
    }

    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])
    parsed = {"workout": "", "history": None, "strategy": "", "scaling": "", "intermediate": "", "beginner": "", "cues": ""}

    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    post_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if post_match:
        parsed['workout'] = workout_text[:post_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    for i, item in enumerate(indices):
        key, start = item['key'], item['end']
        end = indices[i+1]['start'] if (i + 1 < len(indices)) else len(full_blob)
        content = full_blob[start:end].strip()
        if key == "Stimulus": parsed['strategy'] = content
        elif key == "Scaling": parsed['scaling'] = content
        elif key == "Intermediate": parsed['intermediate'] = content
        elif key == "Beginner": parsed['beginner'] = content
        elif key == "Cues": parsed['cues'] = content

    parsed['title'] = wod_data.get('title', 'Workout of the Day')
    parsed['hash'] = hashlib.md5(full_blob.encode()).hexdigest()
    return parsed

# --- STEP 3: ENGINES (Cloudscraper Only - No Sync Yet) ---
# Note: We removed the auto-sync to sheet. We only sync when you click SAVE in Workbench.
def fetch_wod_content():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})

    try:
        response = scraper.get(f"https://www.crossfit.com/{today_id}", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                wod_data = json.loads(next_data.string).get('props', {}).get('pageProps', {}).get('wod', {})
                if wod_data:
                    parsed = parse_workout_data(wod_data)
                    parsed['id'] = today_id
                    return parsed
        return {"error": "Connection Failed"}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER: THE SPLIT ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

if not READY_TO_SYNC:
    st.error("Missing Dependencies: cloudscraper, gspread")
else:
    # --- VIEW MODE: READ ONLY ---
    if st.session_state['view_mode'] == 'VIEWER':
        
        # Only fetch if we haven't already (Cache speedup)
        if not st.session_state['current_wod']:
            with st.spinner("Syncing..."):
                wod = fetch_wod_content()
                st.session_state['current_wod'] = wod
        else:
            wod = st.session_state['current_wod']

        if wod and "workout" in wod:
            st.subheader(wod['title'])
            st.info(wod['workout'])
            
            # The Trigger Button
            if st.button("🚀 IMPORT TO WORKBENCH", use_container_width=True):
                st.session_state['view_mode'] = 'WORKBENCH'
                st.rerun()

            st.divider()
            
            # Read-Only Details
            if wod.get('strategy'):
                with st.expander("Stimulus & Strategy"):
                    st.write(wod['strategy'])
            
            if any([wod.get('scaling'), wod.get('intermediate')]):
                with st.expander("Scaling Options"):
                    st.write(f"**Rx Scaling:** {wod.get('scaling', 'N/A')}")
                    st.write(f"**Intermediate:** {wod.get('intermediate', 'N/A')}")

        else:
            st.error(f"Error: {wod.get('error')}")

    # --- WORKBENCH MODE: EDITABLE (Phase 3 Prep) ---
    elif st.session_state['view_mode'] == 'WORKBENCH':
        st.caption("🛠️ WORKBENCH ACTIVE")
        
        # Grab data from session
        wod = st.session_state['current_wod']
        
        st.success(f"Imported: {wod['title']}")
        st.markdown(f"**Rx Workout:** {wod['workout']}")
        
        st.warning("⚠️ Phase 3 Construction Zone: The Parsing Grid goes here.")
        
        # Back Button
        if st.button("⬅️ Back to Viewer"):
            st.session_state['view_mode'] = 'VIEWER'
            st.rerun()
