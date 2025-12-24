import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 0. CRITICAL DEPENDENCIES (Try/Except for Safety) ---
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

try:
    import cloudscraper
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")

# --- 2. GLOBAL STYLES (High Contrast & Athlete Focus) ---
st.markdown("""
<style>
    div[data-testid="stAlert"], div[data-testid="stNotification"] {
        background-color: #172b4d !important;
        border: 1px solid #3b5e8c !important;
        color: #ffffff !important;
    }
    div[data-testid="stAlert"] *, div[data-testid="stNotification"] * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    .stTextInput input {
        font-weight: bold;
        color: #172b4d !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. THE WHITEBOARD CONNECTION (Google Sheets) ---
def connect_to_whiteboard():
    if not SHEETS_AVAILABLE:
        return None
    
    # We look for secrets in Streamlit Cloud
    if "gcp_service_account" not in st.secrets:
        return None

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # Load credentials from secrets
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Connect to the Master Sheet
        # Replace 'TRI_DRIVE_DATA' with your actual Sheet Name if different
        sheet = client.open("TRI_DRIVE_DATA")
        return sheet
    except Exception as e:
        st.error("Whiteboard Link Error: " + str(e))
        return None

def push_score_to_sheet(wod_title, result_text):
    sheet = connect_to_whiteboard()
    if not sheet:
        return False
        
    try:
        # Select Worksheet #2 (Index 1) for Athlete Logs
        worksheet = sheet.get_worksheet(1)
        
        # Timestamp
        local_tz = pytz.timezone("US/Mountain")
        timestamp = datetime.datetime.now(local_tz).strftime("%Y-%m-%d")
        
        # Payload
        row = [timestamp, wod_title, result_text]
        worksheet.append_row(row)
        return True
    except Exception as e:
        st.error("Upload Failed: " + str(e))
        return False

# --- 4. UTILITY: The Janitor ---
def sanitize_text(text):
    if not text: return ""
    replacements = {"â": "'", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    soup = BeautifulSoup(text, "html.parser")
    for br in soup.find_all("br"): br.replace_with("\n")
    for li in soup.find_all("li"): 
        li.insert_before("\n• ")
        li.insert_after("\n")
    for block in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4']):
        block.insert_before("\n\n")
        block.insert_after("\n\n")
    text = soup.get_text(separator=" ", strip=True)
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("Resources:", "\n\nResources:")
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

# --- 5. CORE LOGIC: The WOD Parser ---
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
    }

    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])
    
    parsed = {
        "workout": "", "strategy": "", "scaling": "", 
        "intermediate": "", "beginner": "", "cues": "",
        "title": title
    }

    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    footer_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if footer_match:
        parsed['workout'] = workout_text[:footer_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    for i, item in enumerate(indices):
        key = item['key']
        start = item['end']
        end = indices[i+1]['start'] if (i + 1 < len(indices)) else len(full_blob)
        content = full_blob[start:end].strip()
        
        if key == "Stimulus": parsed['strategy'] = content
        elif key == "Scaling": parsed['scaling'] = content
        elif key == "Intermediate": parsed['intermediate'] = content
        elif key == "Beginner": parsed['beginner'] = content
        elif key == "Cues": parsed['cues'] = content

    parsed['hash'] = hashlib.md5(full_blob.encode()).hexdigest()
    return parsed

# --- 6. NETWORK: The Fetcher ---
def fetch_wod_content():
    if not SCRAPER_AVAILABLE:
        return {"error": "Scraper Module Missing"}
        
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        url = "https://www.crossfit.com/" + today_id
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            response.encoding = 'utf-8' 
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Strategy A
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                try:
                    json_payload = json.loads(next_data.string)
                    wod_data = json_payload.get('props', {}).get('pageProps', {}).get('wod', {})
                    if wod_data:
                        parsed = parse_workout_data(wod_data)
                        parsed['id'] = today_id
                        return parsed
                except: pass 

            # Strategy B
            article = soup.find('article') or soup.find('div', {'class': re.compile(r'content|wod')}) or soup.find('main')
            if article:
                parsed = parse_workout_data(str(article))
                parsed['id'] = today_id
                parsed['title'] = "WOD " + today_id
                return parsed

            return {"error": "Parser Mismatch."}
        return {"error": "HTTP Error " + str(response.status_code)}
    except Exception as e:
        return {"error": "Critical Failure: " + str(e)}

# --- 7. UI LAYER ---
st.title("TRI⚡DRIVE")
st.markdown("---") 

# --- STATE MANAGEMENT & RECOVERY PROTOCOL ---
if 'app_mode' not in st.session_state:
    st.session_state['app_mode'] = 'HOME'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}
if 'wod_in_progress' not in st.session_state:
    st.session_state['wod_in_progress'] = False

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Box Settings")
    if st.button("🔄 Force Reset", type="primary"):
        st.session_state.clear()
        st.rerun()
    
    # Whiteboard Status Indicator
    if SHEETS_AVAILABLE and "gcp_service_account" in st.secrets:
        st.success("Whiteboard: LINKED")
    else:
        st.warning("Whiteboard: OFFLINE")

# --- APP FLOW ---

# 1. RECOVERY CHECK (The Intercept)
if st.session_state['wod_in_progress'] and st.session_state['app_mode'] == 'HOME':
    st.warning("⚠️ **UNFINISHED WORKOUT DETECTED**")
    st.write("You have an active session in the cache.")
    
    col_res, col_new = st.columns(2)
    with col_res:
        if st.button("RESUME WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.rerun()
    with col_new:
        if st.button("START NEW WOD", use_container_width=True):
            st.session_state['wod_in_progress'] = False
            st.session_state['app_mode'] = 'HOME'
            st.rerun()

# 2. HOME SCREEN (The WOD Board)
elif st.session_state['app_mode'] == 'HOME':
    wod = st.session_state.get('current_wod', {})
    
    if not wod or "error" in wod:
        st.info("📡 Fetching Programming...") 
        wod = fetch_wod_content()
        if "error" not in wod:
            st.session_state['current_wod'] = wod
            st.rerun() 
        else:
            st.error("⚠️ " + str(wod.get('error', 'Unknown Error')))
            if st.button("🔄 Retry Connection"):
                st.session_state['current_wod'] = {}
                st.rerun()
    else:
        # Display WOD
        st.subheader(wod.get('title', 'Daily WOD'))
        formatted_workout = wod.get('workout', 'No Data').replace("\n", "  \n")
        st.info(formatted_workout)
        
        # ACTIVATE BUTTON
        if st.button("⚡ START WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.session_state['wod_in_progress'] = True # Set Flag
            st.rerun()
            
        st.divider()
        # Strategy/Scaling Display
        if wod.get('strategy'):
            with st.expander("Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

# 3. WORKBENCH (Active Athlete Mode)
elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    
    # Header
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    
    # THE KINETIC PARSER
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    
    st.markdown("### 📋 Checklist")
    
    # Dynamic Checkbox Generation
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        # Heuristics
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
            
        # Rendering
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
            
    st.divider()
    
    # LOGGING & EXIT
    st.markdown("#### 🏁 Post Score")
    
    # INPUT FIELD (Added per Requirements Phase 5)
    result_input = st.text_input("Final Time / Load / Score", key="res_input")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ Exit (No Save)"):
            st.session_state['app_mode'] = 'HOME'
            st.rerun()
            
    with c2:
        if st.button("💾 Log to Whiteboard", type="primary"):
            if not result_input:
                st.error("Enter a score to log.")
            else:
                st.toast("Syncing to Cloud...")
                
                # Execute Data Push
                success = push_score_to_sheet(title_safe, result_input)
                
                if success:
                    st.success("Score Posted!")
                    # Clear Progress Flag
                    st.session_state['wod_in_progress'] = False
                    # Delay slightly or just rerun
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed. Check Connection.")

# === END OF SYSTEM FILE ===
   # We take the raw workout text and attempt to structure it
            raw_workout = wod.get('workout', '')
            
            # Safety Check: Ensure string
            if not isinstance(raw_workout, str):
                raw_workout = str(raw_workout)

            # Split by newlines (The Janitor already ensured clean \n separators)
            lines = raw_workout.split('\n')
            
            # PARSING LOOP
            # We track an index 'idx' to create unique keys for every checkbox
            st.markdown("### 📋 Mission Checklist")
            
            for idx, line in enumerate(lines):
                line = line.strip()
                
                # Skip empty noise
                if not line:
                    continue
                    
                # HEURISTIC 1: Detect Headers/Schemes
                # If a line ends in a colon (:) or implies a round structure, it is a header.
                is_header = False
                if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
                    is_header = True
                
                # HEURISTIC 2: Detect Movements
                # If it starts with a number (reps) or a bullet point, it is likely a movement.
                # The Janitor injected "• " for list items, so we look for that.
                is_movement = False
                if line.startswith("•") or line[0].isdigit():
                    is_movement = True
                
                # RENDER LOGIC
                if is_header and not is_movement:
                    # Render as bold instruction using concatenation
                    st.markdown("**" + line + "**")
                
                elif is_movement:
                    # Render as Checkbox
                    # Key generation uses strict unique ID to prevent state collision
                    # NO F-STRINGS: "chk_" + str(idx)
                    checkbox_key = "chk_" + str(idx)
                    
                    # Clean the bullet for display if present
                    display_text = line.replace("• ", "").strip()
                    
                    st.checkbox(display_text, key=checkbox_key)
                    
                else:
                    # Fallback: Render as standard text note
                    st.markdown(line)

            st.divider()
            
            # 4. NAVIGATION
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Abort & Return"):
                    st.session_state['view_mode'] = 'VIEWER'
                    st.rerun()
            with col2:
                # Placeholder for Phase 4
                st.button("💾 Save to Log (Locked)", disabled=True)

# === END OF SYSTEM FILE ===
