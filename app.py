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
    
    if "gcp_service_account" not in st.secrets:
        return None

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
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
        worksheet = sheet.get_worksheet(1)
        local_tz = pytz.timezone("US/Mountain")
        timestamp = datetime.datetime.now(local_tz).strftime("%Y-%m-%d")
        row = [timestamp, wod_title, result_text]
        worksheet.append_row(row)
        return True
    except Exception as e:
        st.error("Upload Failed: " + str(e))
        return False

# --- 4. UTILITY: The Janitor (Safe Mode) ---
def sanitize_text(text):
    if not text: return ""
    
    # 1. Clean weird quote characters
    replacements = {"â": "'", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}
    for bad, good in replacements.items():
        text = text.replace(bad, good)
        
    soup = BeautifulSoup(text, "html.parser")
    
    # 2. Structural Spacing (HTML Level)
    for tag in soup.find_all(['br', 'p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'tr']):
        tag.insert_before("\n")
        tag.insert_after("\n")
        
    for li in soup.find_all('li'):
        li.insert_before("• ")

    # 3. Extract text
    text = soup.get_text(separator="\n", strip=True)
    text = unicodedata.normalize("NFKD", text)
    
    # 4. General Cleanup
    text = text.replace("Resources:", "\n\n**Resources:**\n")
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

# --- 5. CORE LOGIC: The Context-Aware Mapper ---
def parse_workout_data(wod_data):
    # Step 1: Sanitize the blob safely (HTML only)
    if isinstance(wod_data, str):
        full_blob = sanitize_text(wod_data)
        title = "Workout of the Day"
    else:
        raw_main = wod_data.get('main_text', '')
        raw_stim = wod_data.get('stimulus', '')
        full_blob = sanitize_text(raw_main + "\n\n" + raw_stim)
        title = wod_data.get('title', 'Workout of the Day')

    # Step 2: Slice the blob into sections
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
    
    # Step 3: AGGRESSIVE FORMATTING (Applied ONLY to the Workout)
    raw_workout = full_blob[:workout_end].strip()
    
    # The "Mashed Number" Fix: Only runs on the workout list
    # Finds a lowercase letter -> space -> number -> space/letter
    # Ex: "walk 2 candlestick" -> "walk\n2 candlestick"
    formatted_workout = re.sub(r'(?<=[a-z])\s+(?=\d+\s+[a-zA-Z])', '\n', raw_workout)
    parsed['workout'] = formatted_workout

    # Footer cleanup
    footer_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+to\s+comments)", parsed['workout'], re.IGNORECASE)
    if footer_match:
        parsed['workout'] = parsed['workout'][:footer_match.start()].strip()

    # Step 4: Map the rest (Keeping Scaling/Strategy natural)
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

# --- STATE MANAGEMENT ---
if 'app_mode' not in st.session_state:
    st.session_state['app_mode'] = 'HOME'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}
if 'wod_in_progress' not in st.session_state:
    st.session_state['wod_in_progress'] = False

# Sidebar
with st.sidebar:
    st.header("⚙️ Box Settings")
    if st.button("🔄 Force Reset", type="primary"):
        st.session_state.clear()
        st.rerun()
    if SHEETS_AVAILABLE and "gcp_service_account" in st.secrets:
        st.success("Whiteboard: LINKED")
    else:
        st.warning("Whiteboard: OFFLINE")

# --- APP FLOW ---

# 1. RECOVERY
if st.session_state['wod_in_progress'] and st.session_state['app_mode'] == 'HOME':
    st.warning("⚠️ **UNFINISHED WORKOUT DETECTED**")
    st.write("You have an active session in the cache.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("RESUME WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.rerun()
    with c2:
        if st.button("START NEW WOD", use_container_width=True):
            st.session_state['wod_in_progress'] = False
            st.session_state['app_mode'] = 'HOME'
            st.rerun()

# 2. HOME SCREEN
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
        st.subheader(wod.get('title', 'Daily WOD'))
        
        # UI FORMATTING FIX
        raw_workout = wod.get('workout', 'No Data')
        # Double space replacement for Streamlit Markdown
        formatted_workout = raw_workout.replace("\n", "  \n")
        st.info(formatted_workout)
        
        if st.button("⚡ START WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.session_state['wod_in_progress'] = True 
            st.rerun()
            
        st.divider()
        if wod.get('strategy'):
            with st.expander("🧠 Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("⚖️ Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

        if wod.get('cues'):
            with st.expander("📢 Coaching Cues"):
                st.markdown(wod['cues'].replace("\n", "  \n"))

# 3. WORKBENCH
elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    
    st.markdown("### 📋 Checklist")
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
            
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
            
    st.divider()
    st.markdown("#### 🏁 Post Score")
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
                success = push_score_to_sheet(title_safe, result_input)
                if success:
                    st.success("Score Posted!")
                    st.session_state['wod_in_progress'] = False
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed.")

# === END OF SYSTEM FILE ===
```Okay, I'll make a note of that in my memory.

In case you wanted to save this as a custom instruction, you can manually add that in your [personal context settings](https://gemini.google.com/personal-context).
t.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))
        if wod.get('cues'):
            with st.expander("📢 Coaching Cues"):
                st.markdown(wod['cues'].replace("\n", "  \n"))

elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    st.markdown("### 📋 Checklist")
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
    st.divider()
    st.markdown("#### 🏁 Post Score")
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
                success = push_score_to_sheet(title_safe, result_input)
                if success:
                    st.success("Score Posted!")
                    st.session_state['wod_in_progress'] = False
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed.")
xpander("🧠 Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("⚖️ Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

        if wod.get('cues'):
            with st.expander("📢 Coaching Cues"):
                st.markdown(wod['cues'].replace("\n", "  \n"))

# 3. WORKBENCH
elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    
    st.markdown("### 📋 Checklist")
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
            
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
            
    st.divider()
    st.markdown("#### 🏁 Post Score")
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
                success = push_score_to_sheet(title_safe, result_input)
                if success:
                    st.success("Score Posted!")
                    st.session_state['wod_in_progress'] = False
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed.")
      st.session_state['app_mode'] = 'WORKBENCH'
            st.session_state['wod_in_progress'] = True 
            st.rerun()
            
        st.divider()
        if wod.get('strategy'):
            with st.expander("🧠 Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("⚖️ Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

        if wod.get('cues'):
            with st.expander("📢 Coaching Cues"):
                st.markdown(wod['cues'].replace("\n", "  \n"))

# 3. WORKBENCH
elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    
    st.markdown("### 📋 Checklist")
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
            
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
            
    st.divider()
    st.markdown("#### 🏁 Post Score")
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
                success = push_score_to_sheet(title_safe, result_input)
                if success:
                    st.success("Score Posted!")
                    st.session_state['wod_in_progress'] = False
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed.")

# === END OF SYSTEM FILE ===
```Okay, I'll make a note of that in my memory.

In case you wanted to save this as a custom instruction, you can manually add that in your [personal context settings](https://gemini.google.com/personal-context).
ent_wod'] = {}
                st.rerun()
    else:
        # --- TITLE SECTION ---
        st.subheader(wod.get('title', 'Daily WOD'))
        
        # --- WORKOUT DISPLAY (With Visual Formatting) ---
        raw_workout = wod.get('workout', 'No Data')
        # Force double spaces for Streamlit markdown breaks
        formatted_workout = raw_workout.replace("\n", "  \n")
        st.info(formatted_workout)
        
        # ACTIVATE BUTTON
        if st.button("⚡ START WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.session_state['wod_in_progress'] = True # Set Flag
            st.rerun()
            
        st.divider()
        # Strategy/Scaling Display
        if wod.get('strategy'):
            with st.expander("🧠 Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("⚖️ Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

        if wod.get('cues'):
            with st.expander("📢 Coaching Cues"):
                st.markdown(wod['cues'].replace("\n", "  \n"))

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
    
    # INPUT FIELD
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
