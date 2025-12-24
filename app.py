import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION (CRITICAL: MUST BE FIRST) ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")

# --- 2. GLOBAL STYLES (High Contrast / White on Blue) ---
st.markdown("""
<style>
    /* Force Deep Blue Background & White Text for Info Boxes */
    [data-testid="stNotification"] {
        background-color: #172b4d;
        border: 1px solid #3b5e8c;
        color: #ffffff !important;
    }
    /* Force Paragraphs inside Info Boxes to be White */
    [data-testid="stNotification"] p {
        color: #ffffff !important;
        font-size: 16px;
        line-height: 1.6;
    }
    /* Force Lists inside Info Boxes to be White */
    [data-testid="stMarkdownContainer"] ul, 
    [data-testid="stMarkdownContainer"] li {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DIAGNOSTICS & RESET ---
with st.sidebar:
    st.header("🔧 System Operations")
    if st.button("⚠️ Hard Reset System", type="primary"):
        st.session_state.clear()
        st.rerun()

# --- 4. DEPENDENCY CHECK ---
try:
    import cloudscraper
    READY_TO_SYNC = True
    st.sidebar.success("Core Systems: ONLINE")
except ImportError:
    READY_TO_SYNC = False
    st.sidebar.error("Core Systems: OFFLINE (Missing cloudscraper)")

# --- 5. SESSION STATE INITIALIZATION ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'VIEWER'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}

# --- 6. UTILITY: The Sanitizer (Strict Formatting) ---
def sanitize_text(text):
    if not text: return ""
    
    # A. Artifact Replacement (Smart Quotes -> Standard)
    replacements = {
        "â": "'", "’": "'", "‘": "'", 
        "“": '"', "”": '"', 
        "–": "-", "—": "-", "…": "..."
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # B. Structural Parsing
    soup = BeautifulSoup(text, "html.parser")
    
    # Insert double newlines after block elements to force spacing
    for tag in soup.find_all(['p', 'div', 'li']):
        tag.insert_after("\n\n")
        
    # Convert breaks to single newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")
        
    # Extract text
    text = soup.get_text(separator="", strip=True) 
    
    # C. Normalization & Cleanup
    text = unicodedata.normalize("NFKD", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

# --- 7. CORE LOGIC: The Mapper ---
def parse_workout_data(wod_data):
    # Normalize input types
    if isinstance(wod_data, str):
        full_blob = sanitize_text(wod_data)
        title = "Workout of the Day"
    else:
        raw_main = wod_data.get('main_text', '')
        raw_stim = wod_data.get('stimulus', '')
        full_blob = sanitize_text(raw_main + "\n\n" + raw_stim)
        title = wod_data.get('title', 'Workout of the Day')

    # Regex Compilation (Strict)
    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE)
    }

    # Section Indexing
    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])
    
    # Default Schema
    parsed = {
        "workout": "", 
        "strategy": "", 
        "scaling": "", 
        "intermediate": "", 
        "beginner": "", 
        "cues": "",
        "title": title
    }

    # Extract Main Workout
    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    # Truncate Footer
    footer_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if footer_match:
        parsed['workout'] = workout_text[:footer_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    # Extract Sections Loop
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

# --- 8. NETWORK LAYER: The Fetcher ---
def fetch_wod_content():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        url = f"https://www.crossfit.com/{today_id}"
        response = scraper.get(url, timeout=15)
        
        if response.status_code == 200:
            response.encoding = 'utf-8' # Force Encoding Fix
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Strategy A: JSON Data extraction
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

            # Strategy B: HTML Fallback
            article = soup.find('article') or soup.find('div', {'class': re.compile(r'content|wod')}) or soup.find('main')
            if article:
                parsed = parse_workout_data(str(article))
                parsed['id'] = today_id
                parsed['title'] = f"WOD {today_id}"
                return parsed

            return {"error": "Parser Mismatch: Content detected but structure unknown."}

        return {"error": f"HTTP Error {response.status_code}"}
        
    except Exception as e:
        return {"error": f"Critical Failure: {str(e)}"}

# --- 9. UI LAYER: The Interface ---
st.title("TRI⚡DRIVE")
st.markdown("---") 

if not READY_TO_SYNC:
    st.error("SYSTEM HALTED: Critical dependencies missing.")
else:
    # === VIEWER MODE ===
    if st.session_state['view_mode'] == 'VIEWER':
        
        # Data Retrieval with Validation
        wod = st.session_state.get('current_wod', {})
        
        if not wod or "error" in wod:
            st.info("📡 Establishing Secure Connection...") 
            wod = fetch_wod_content()
            
            if "error" not in wod:
                st.session_state['current_wod'] = wod
                st.rerun() 
            else:
                st.error(f"⚠️ {wod['error']}")
                if st.button("🔄 Retry Handshake"):
                    st.session_state['current_wod'] = {}
                    st.rerun()
        else:
            # === RENDER: SUCCESS ===
            if "workout" in wod:
                st.subheader(wod['title'])
                
                # Main WOD Box (White Text Forced)
                # Using Markdown double-space for line breaks
                formatted_workout = wod['workout'].replace("\n", "  \n")
                st.info(formatted_workout) 
                
                # Workbench Trigger
                if st.button("🚀 IMPORT TO WORKBENCH", use_container_width=True):
                    st.session_state['view_mode'] = 'WORKBENCH'
                    st.rerun()

                st.divider()
                
                # Strategy Section
                if wod.get('strategy'):
                    with st.expander("Stimulus & Strategy"):
                        st.markdown(wod['strategy'].replace("\n", "  \n"))
                
                # Scaling Section (Tabbed Interface)
                has_scaling = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
                if has_scaling:
                    with st.expander("Scaling Options", expanded=False):
                        tab_rx, tab_int, tab_beg = st.tabs(["Rx / General", "Intermediate", "Beginner"])
                        
                        with tab_rx:
                            content = wod.get('scaling') or "No specific Rx instructions."
                            st.markdown(content.replace("\n", "  \n"))
                                
                        with tab_int:
                            content = wod.get('intermediate') or "No Intermediate option."
                            st.markdown(content.replace("\n", "  \n"))
                                
                        with tab_beg:
                            content = wod.get('beginner') or "No Beginner option."
                            st.markdown(content.replace("\n", "  \n"))

                # Coaching Cues Section
                if wod.get('cues'):
                    with st.expander("Coaching Cues"):
                        st.markdown(wod['cues'].replace("\n", "  \n"))

            else:
                st.error("Data integrity failure. Perform Hard Reset.")

    # === WORKBENCH MODE ===
    elif st.session_state['view_mode'] == 'WORKBENCH':
        st.caption("🛠️ WORKBENCH ACTIVE")
        wod = st.session_state.get('current_wod', {})
        
        if not wod:
            st.error("Memory buffer empty.")
            if st.button("Return to Base"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
        else:
            st.success(f"Loaded: {wod.get('title', 'Unknown')}")
            
            # Preview (Formatted)
            formatted_rx = wod.get('workout', 'No Data').replace("\n", "  \n")
            st.markdown(f"**Target Workout:** \n{formatted_rx}")
            
            st.warning("⚠️ Phase 3 Pending Authorization")
            
            if st.button("⬅️ Abort & Return"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
