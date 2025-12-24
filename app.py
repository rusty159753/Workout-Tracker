import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz
import unicodedata

# --- THE JANITOR (Sanitization Function) ---
def sanitize_text(text):
    if not text:
        return ""
    
    # 1. Normalize Unicode (Fixes encoding artifacts like â□□)
    # NFKD form decomposes characters into their base components
    text = unicodedata.normalize("NFKD", text)
    
    # 2. HARD REPLACE: Turn non-breaking spaces (\xa0) into real spaces
    # This is critical for our regex to work later
    text = text.replace('\xa0', ' ')
    
    # 3. Collapse multiple spaces into one clean space
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def execute_sanitization_test():
    # Standard setup
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    target_url = f"https://www.crossfit.com/{today_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        
        # *** STEP 1: FORCE ENCODING ***
        response.encoding = 'utf-8'

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    # Capture the RAW blob (Dirty)
                    raw_main = wod_data.get('main_text', '')
                    raw_stim = wod_data.get('stimulus', '')
                    full_raw_blob = raw_main + " " + raw_stim
                    
                    # Run the JANITOR (Clean)
                    clean_blob = sanitize_text(full_raw_blob)
                    
                    return {
                        "status": "success",
                        "raw": full_raw_blob,
                        "clean": clean_blob,
                        "id": today_id
                    }

        return {"status": "error", "message": f"Could not fetch WOD (Status {response.status_code})"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- UI LAYER (Diagnostic Mode) ---
st.set_page_config(page_title="TRI DRIVE: Janitor Mode", page_icon="🧹")
st.title("🧹 Sanitization Diagnostic")

if st.button("Run Sanity Check"):
    with st.spinner("Fetching and scrubbing data..."):
        result = execute_sanitization_test()
    
    if result['status'] == 'success':
        # 1. GHOST HUNTING
        # Count invisible characters in the RAW text
        ghost_count = result['raw'].count('\xa0')
        
        st.success(f"Connection Successful: /{result['id']}")
        
        # 2. THE REPORT CARD
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Ghost Spaces Found", ghost_count)
        with col2:
            st.metric("Encoding Verified", "UTF-8")

        st.divider()

        # 3. VISUAL COMPARISON
        st.subheader("Results")
        
        st.markdown("### ❌ Raw Data (Potential Garbage)")
        # We start with a warning if we see the 'â' character usually associated with the error
        if 'â' in result['raw']:
            st.error("Detected Encoding Artifacts (â□□) in Raw Data!")
        else:
            st.warning("Raw Data Stream")
        st.code(result['raw'], language=None)

        st.markdown("### ✅ Sanitized Data (Clean English)")
        st.success("Ready for Parsing")
        st.info(result['clean'])
        
    else:
        st.error(f"Fetch Failed: {result['message']}")
