import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 0. SAFETY CONSTANTS ---
# We use this constant to prevent syntax errors with backslashes
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
    Safely formats text for Streamlit Markdown.
    """
    if not text:
        return ""
    # Convert newlines using the safe constant
    return str(text).replace("\n", NL)

def connect_to_whiteboard():
    if not SHEETS_AVAILABLE: return None
    if "gcp_service_account" not in st.secrets: return None
    
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

# --- 5. PARSING ENGINE ---

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

# --- 7. UI MODULES (EARLY RETURN LOGIC) ---

def render_home():
    """Renders the Home Screen. Uses Early Returns (No Else)."""
    wod = st.session_state.get('current_wod', {})
    
    # 1. Fetch Logic
    if not wod or "error" in wod:
        st.info("📡 Fetching Programming...") 
        wod = fetch_wod_content()
        
        if "error" in wod:
            st.error(wod['error'])
            if st.button("Retry"):
                st.session_state['current_wod'] = {}
                st.rerun()
            return # Stop execution here
            
        # If success
        st.session_state['current_wod'] = wod
        st.rerun()
        return

    # 2. Display Logic
    st.subheader(wod.get('title', 'WOD'))
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
        
    # Scaling
    has_scale = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
    if has_scale:
        st.caption("⚖️ Scaling")
        t1, t2, t3 = st.tabs(["Rx", "Int", "Beg"])
        
        t1.markdown(safe_format(wod.get('scaling', '')))
        t2.markdown(safe_format(wod.get('intermediate', '')))
        t3.markdown(safe_format(wod.get('beginner', '')))
        
    # Cues
    if wod.get('cues'):
        cue_text = safe_format(wod['cues'])
        st.expander("📢 Cues").markdown(cue_text)

def render_workbench():
    """Renders the Active Session."""
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

# --- 8. MAIN ENTRY POINT ---

def main():
    # Initialize State
    if 'app_mode' not in st.session_state: st.session_state['app_mode'] = 'HOME'
    if 'current_wod' not in st.session_state: st.session_state['current_wod'] = {}
    if 'wod_in_progress' not in st.session_state: st.session_state['wod_in_progress'] = False

    # Sidebar
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

    # Routing
    if st.session_state['app_mode'] == 'HOME':
        render_home()
        return

    if st.session_state['app_mode'] == 'WORKBENCH':
        render_workbench()
        return

if __name__ == "__main__":
    main()
    
