import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 0. SAFETY CONSTANTS (The "Invisible" Fix) ---
# We define special characters here so they don't break logic later
NL = "  \n"

# --- 1. CRITICAL DEPENDENCIES ---
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

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")

# --- 3. GLOBAL STYLES ---
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

# --- 4. UTILITY MODULES ---

def safe_format(text):
    """
    The firewall for text. Converts raw text to Markdown-safe text
    using the global NL constant. No backslashes in UI code.
    """
    if not text:
        return ""
    return str(text).replace("\n", NL)

def connect_to_whiteboard():
    if not SHEETS_AVAILABLE or "gcp_service_account" not in st.secrets:
        return None
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("TRI_DRIVE_DATA")
    except Exception as e:
        st.error(f"Whiteboard Error: {e}")
        return None

def push_score_to_sheet(wod_title, result_text):
    sheet = connect_to_whiteboard()
    if not sheet: return False
    try:
        ws = sheet.get_worksheet(1)
        tz = pytz.timezone("US/Mountain")
        now = datetime.datetime.now(tz).strftime("%Y-%m-%d")
        ws.append_row([now, wod_title, result_text])
        return True
    except Exception as e:
        st.error(f"Sync Failed: {e}")
        return False

# --- 5. PARSING ENGINE (Janitor Logic) ---

def sanitize_text(text):
    if not text: return ""
    
    # Character normalization
    chars = {"â": "'", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"}
    for b, g in chars.items():
        text = text.replace(b, g)
        
    soup = BeautifulSoup(text, "html.parser")
    
    # Structure enforcement
    for tag in soup.find_all(['br', 'p', 'div', 'li', 'h1', 'h2', 'tr']):
        tag.insert_before("\n")
        tag.insert_after("\n")
        
    for li in soup.find_all('li'):
        li.insert_before("• ")

    text = soup.get_text(separator="\n", strip=True)
    text = unicodedata.normalize("NFKD", text)
    return text.replace("Resources:", "\n\n**Resources:**\n").strip()

def parse_workout_data(wod_data):
    # Input normalization
    if isinstance(wod_data, str):
        blob = sanitize_text(wod_data)
        title = "Workout of the Day"
    else:
        m = wod_data.get('main_text', '')
        s = wod_data.get('stimulus', '')
        blob = sanitize_text(m + "\n\n" + s)
        title = wod_data.get('title', 'Workout of the Day')

    # Regex Extraction Patterns
    patterns = {
        "Stimulus": r"(Stimulus\s+and\s+Strategy|Stimulus):",
        "Scaling": r"(Scaling|Scaling Options):",
        "Intermediate": r"Intermediate\s+option:",
        "Beginner": r"Beginner\s+option:",
        "Cues": r"(Coaching\s+cues|Coaching\s+Tips):"
    }

    indices = []
    for k, p in patterns.items():
        match = re.search(p, blob, re.IGNORECASE)
        if match:
            indices.append({"key": k, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])
    
    # Result Container
    parsed = {
        "workout": "", "strategy": "", "scaling": "", 
        "intermediate": "", "beginner": "", "cues": "", 
        "title": title
    }

    # Extract WOD List
    w_end = indices[0]['start'] if indices else len(blob)
    raw_w = blob[:w_end].strip()
    # The "Mashed Line" Fix
    parsed['workout'] = re.sub(r'(?<=[a-z])\s+(?=\d+\s+[a-zA-Z])', '\n', raw_w)

    # Extract Sections
    for i, item in enumerate(indices):
        k = item['key']
        s = item['end']
        e = indices[i+1]['start'] if (i+1 < len(indices)) else len(blob)
        content = blob[s:e].strip()
        
        if k == "Stimulus": parsed['strategy'] = content
        elif k == "Scaling": parsed['scaling'] = content
        elif k == "Intermediate": parsed['intermediate'] = content
        elif k == "Beginner": parsed['beginner'] = content
        elif k == "Cues": parsed['cues'] = content

    parsed['hash'] = hashlib.md5(blob.encode()).hexdigest()
    return parsed

# --- 6. NETWORK MODULE ---

def fetch_wod_content():
    if not SCRAPER_AVAILABLE: return {"error": "Scraper Missing"}
    
    tz = pytz.timezone("US/Mountain")
    tid = datetime.datetime.now(tz).strftime("%y%m%d")
    scraper = cloudscraper.create_scraper()
    
    try:
        url = "https://www.crossfit.com/" + tid
        res = scraper.get(url, timeout=15)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # JSON Strategy
            script = soup.find('script', id='__NEXT_DATA__')
            if script:
                try:
                    data = json.loads(script.string).get('props', {}).get('pageProps', {}).get('wod', {})
                    if data:
                        parsed = parse_workout_data(data)
                        parsed['id'] = tid
                        return parsed
                except: pass
            
            # HTML Strategy
            article = soup.find('article') or soup.find('main')
            if article:
                parsed = parse_workout_data(str(article))
                parsed['id'] = tid
                return parsed
                
        return {"error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --- 7. UI MODULES (Indentation Safe) ---

def render_home():
    """Renders the Home Screen. Flat indentation."""
    wod = st.session_state.get('current_wod', {})
    
    # 1. Fetch Logic
    if not wod or "error" in wod:
        st.info("📡 Fetching Programming...") 
        wod = fetch_wod_content()
        if "error" not in wod:
            st.session_state['current_wod'] = wod
            st.rerun()
        else:
            st.error(wod['error'])
            if st.button("Retry"):
                st.session_state['current_wod'] = {}
                st.rerun()
        return

    # 2. Display Logic
    st.subheader(wod.get('title', 'WOD'))
    
    # SAFE FORMATTING: Using the helper function
    main_text = safe_format(wod.get('workout', ''))
    st.info(main_text)
    
    if st.button("⚡ START", use_container_width=True):
        st.session_state['app_mode'] = 'WORKBENCH'
        st.session_state['wod_in_progress'] = True 
        st.rerun()
        
    st.divider()
    
    # Strategy
    if wod.get('strategy'):
        strat_text = safe_format(wod['strategy'])
        st.expander("🧠 Strategy").markdown(strat_text)
        
    # Scaling (Decoupled & Safe)
    has_scale = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
    if has_scale:
        st.caption("⚖️ Scaling")
        t1, t2, t3 = st.tabs(["Rx", "Int", "Beg"])
        
        txt_rx = safe_format(wod.get('scaling', ''))
        txt_int = safe_format(wod.get('intermediate', ''))
        txt_beg = safe_format(wod.get('beginner', ''))
        
        t1.markdown(txt_rx)
        t2.markdown(txt_int)
        t3.markdown(txt_beg)
        
    # Cues
    if wod.get('cues'):
        cue_text = safe_format(wod['cues'])
        st.expander("📢 Cues").markdown(cue_text)

def render_workbench():
    """Renders the Active Session. Flat indentation."""
    wod = st.session_state.get('current_wod', {})
    st.success("Target: " + wod.get('title', 'WOD'))
    
    lines = str(wod.get('workout', '')).split('\n')
    st.markdown("### 📋 Checklist")
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        if line.endswith(":") or "rounds" in line.lower():
            st.markdown(f"**{line}**")
        elif line.startswith("•") or line[0].isdigit():
            # Clean bullet points
            clean = line.replace("• ", "").strip()
            st.checkbox(clean, key=f"chk_{idx}")
        else:
            st.text(line)
            
    st.divider()
    res = st.text_input("Score", key="res_input")
    
    c1, c2 = st.columns(2)
    if c1.button("❌ Exit"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()
        
    if c2.button("💾 Log", type="primary"):
        if res and push_score_to_sheet(wod.get('title', 'WOD'), res):
            st.success("Logged!")
            st.session_state['wod_in_progress'] = False
            st.session_state['app_mode'] = 'HOME'
            st.rerun()

# --- 8. MAIN APP CONTROLLER ---

def main():
    # Initialize State
    if 'app_mode' not in st.session_state: st.session_state['app_mode'] = 'HOME'
    if 'current_wod' not in st.session_state: st.session_state['current_wod'] = {}
    if 'wod_in_progress' not in st.session_state: st.session_state['wod_in_progress'] = False

    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ Box Settings")
        if st.button("🔄 Force Reset"):
            st.session_state.clear()
            st.rerun()

    # Recovery Logic
    if st.session_state['wod_in_progress'] and st.session_state['app_mode'] == 'HOME':
        st.warning("⚠️ UNFINISHED SESSION")
        c1, c2 = st.columns(2)
        if c1.button("RESUME"):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.rerun()
        if c2.button("NEW WOD"):
            st.session_state['wod_in_progress'] = False
            st.rerun()
        return

    # Router
    if st.session_state['app_mode'] == 'HOME':
        render_home()
    elif st.session_state['app_mode'] == 'WORKBENCH':
        render_workbench()

if __name__ == "__main__":
    main()

    else:
        # Display WOD
        st.subheader(wod.get('title', 'Daily WOD'))
        
        # Use Helper Function to Avoid Syntax Errors
        formatted_workout = format_multiline(wod.get('workout', 'No Data'))
        st.info(formatted_workout)
        
        if st.button("⚡ START WORKOUT", use_container_width=True):
            st.session_state['app_mode'] = 'WORKBENCH'
            st.session_state['wod_in_progress'] = True 
            st.rerun()
            
        st.divider()
        
        # Strategy Section (Flattened)
        if wod.get('strategy'):
            strat_exp = st.expander("🧠 Stimulus & Strategy")
            strat_txt = format_multiline(wod['strategy'])
            strat_exp.markdown(strat_txt)
        
        # Scaling Section (Flattened & Protected)
        has_scaling = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
        
        if has_scaling:
            st.caption("⚖️ Scaling Options")
            # Create Tabs directly
            t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
            
            # Use Helper Function instead of replace()
            # This keeps the line short and safe from syntax wrapping
            txt_rx = format_multiline(wod.get('scaling', ''))
            txt_int = format_multiline(wod.get('intermediate', ''))
            txt_beg = format_multiline(wod.get('beginner', ''))
            
            # Render to Tabs
            t1.markdown(txt_rx)
            t2.markdown(txt_int)
            t3.markdown(txt_beg)

        # Cues Section (Flattened)
        if wod.get('cues'):
            cues_exp = st.expander("📢 Coaching Cues")
            cues_txt = format_multiline(wod['cues'])
            cues_exp.markdown(cues_txt)

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
        
        # Header Detection
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        # Movement Detection
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
    
    # Flattened Exit/Save Logic
    c1, c2 = st.columns(2)
    
    if c1.button("❌ Exit (No Save)"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()

    if c2.button("💾 Log to Whiteboard", type="primary"):
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
 = True 
            st.rerun()
            
        st.divider()
        
        # Strategy Section (Flattened)
        if wod.get('strategy'):
            strat_exp = st.expander("🧠 Stimulus & Strategy")
            strat_txt = wod['strategy'].replace("\n", "  \n")
            strat_exp.markdown(strat_txt)
        
        # Scaling Section (Flattened & Decoupled)
        has_scaling = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
        
        if has_scaling:
            st.caption("⚖️ Scaling Options")
            # Create Tabs directly
            t1, t2, t3 = st.tabs(["Rx / General", "Intermediate", "Beginner"])
            
            # Prepare Text Variables (Prevents Line Wrapping Errors)
            txt_rx = str(wod.get('scaling', '')).replace("\n", "  \n")
            txt_int = str(wod.get('intermediate', '')).replace("\n", "  \n")
            txt_beg = str(wod.get('beginner', '')).replace("\n", "  \n")
            
            # Render to Tabs
            t1.markdown(txt_rx)
            t2.markdown(txt_int)
            t3.markdown(txt_beg)

        # Cues Section (Flattened)
        if wod.get('cues'):
            cues_exp = st.expander("📢 Coaching Cues")
            cues_txt = wod['cues'].replace("\n", "  \n")
            cues_exp.markdown(cues_txt)

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
        
        # Header Detection
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        # Movement Detection
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
    
    # Flattened Exit/Save Logic
    c1, c2 = st.columns(2)
    
    if c1.button("❌ Exit (No Save)"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()

    if c2.button("💾 Log to Whiteboard", type="primary"):
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
rkdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
            t3.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

        # Cues (Flattened)
        if wod.get('cues'):
            cues_exp = st.expander("📢 Coaching Cues")
            cues_exp.markdown(wod['cues'].replace("\n", "  \n"))

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
    # Direct Button Calls (No 'with')
    if c1.button("❌ Exit (No Save)"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()

    if c2.button("💾 Log to Whiteboard", type="primary"):
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
\n"))

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
    if c1.button("❌ Exit (No Save)"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()

    if c2.button("💾 Log to Whiteboard", type="primary"):
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
    # FLATTENED LOGIC (Fixes Indentation Risk)
    if c1.button("❌ Exit (No Save)"):
        st.session_state['app_mode'] = 'HOME'
        st.rerun()

    if c2.button("💾 Log to Whiteboard", type="primary"):
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
t.tabs(["Rx / General", "Intermediate", "Beginner"])
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
