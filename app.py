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

    parsed['title'] = title
    parsed['hash'] = hashlib.md5(full_blob.encode()).hexdigest()
    return parsed

# --- 6. ENGINES ---
def fetch_wod_content():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        url = f"https://www.crossfit.com/{today_id}"
        response = scraper.get(url, timeout=10)
        
        if response.status_code == 200:
            response.encoding = 'utf-8' 
            html_text = response.text

            soup = BeautifulSoup(html_text, 'html.parser')
            
            # ATTEMPT 1: JSON
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                try:
                    json_payload = json.loads(next_data.string)
                    wod_data = json_payload.get('props', {}).get('pageProps', {}).get('wod', {})
                    if wod_data:
                        parsed = parse_workout_data(wod_data)
                        parsed['id'] = today_id
                        return parsed
                except:
                    pass

            # ATTEMPT 2: HTML
            article = soup.find('article') or soup.find('div', {'class': re.compile(r'content|wod')}) or soup.find('main')
            if article:
                raw_html = str(article)
                parsed = parse_workout_data(raw_html)
                parsed['id'] = today_id
                parsed['title'] = f"WOD {today_id}"
                return parsed

            page_title = soup.title.string.strip() if soup.title else "No Title"
            return {"error": f"Parsers failed. Page Title: '{page_title}'"}

        return {"error": f"Status {response.status_code}"}
        
    except Exception as e:
        return {"error": f"Error: {str(e)}"}

# --- 7. UI LAYER ---
st.title("TRI⚡DRIVE")
st.write("---") 

if not READY_TO_SYNC:
    st.error("Missing Dependencies")
else:
    # --- VIEW MODE ---
    if st.session_state['view_mode'] == 'VIEWER':
        
        cached_data = st.session_state.get('current_wod', {})
        
        if not cached_data or "error" in cached_data:
            st.info("📡 Connecting to Headquarters...") 
            wod = fetch_wod_content()
            
            if "error" not in wod:
                st.session_state['current_wod'] = wod
                st.rerun() 
            else:
                st.error(f"⚠️ {wod['error']}")
                if st.button("🔄 Retry Connection"):
                    st.session_state['current_wod'] = {}
                    st.rerun()
        else:
            # RENDER SUCCESS STATE
            wod = cached_data
            if "workout" in wod:
                st.subheader(wod['title'])
                
                # --- WOD DISPLAY (White Text via CSS) ---
                # Double space for markdown line breaks
                formatted_workout = wod['workout'].replace("\n", "  \n")
                st.info(formatted_workout) 
                
                if st.button("🚀 IMPORT TO WORKBENCH", use_container_width=True):
                    st.session_state['view_mode'] = 'WORKBENCH'
                    st.rerun()

                st.divider()
                
                # --- STRATEGY ---
                if wod.get('strategy'):
                    with st.expander("Stimulus & Strategy"):
                        st.markdown(wod['strategy'].replace("\n", "  \n"))
                
                # --- SCALING (TABS RESTORED) ---
                # This checks if ANY scaling info exists
                if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
                    with st.expander("Scaling Options", expanded=False):
                        tab_rx, tab_int, tab_beg = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                        
                        with tab_rx:
                            if wod.get('scaling'):
                                st.markdown(wod['scaling'].replace("\n", "  \n"))
                            else:
                                st.caption("No specific Rx scaling instructions.")
                                
                        with tab_int:
                            if wod.get('intermediate'):
                                st.markdown(wod['intermediate'].replace("\n", "  \n"))
                            else:
                                st.caption("No Intermediate option listed.")
                                
                        with tab_beg:
                            if wod.get('beginner'):
                                st.markdown(wod['beginner'].replace("\n", "  \n"))
                            else:
                                st.caption("No Beginner option listed.")

                # --- COACHING CUES (RESTORED) ---
                if wod.get('cues'):
                    with st.expander("Coaching Cues"):
                        st.markdown(wod['cues'].replace("\n", "  \n"))

            else:
                st.error("Data Corrupted. Please hit Hard Reset.")

    # --- WORKBENCH MODE ---
    elif st.session_state['view_mode'] == 'WORKBENCH':
        st.caption("🛠️ WORKBENCH ACTIVE")
        wod = st.session_state.get('current_wod', {})
        
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
