import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. TARGETED SEARCH & ROLLBACK ENGINE ---
def execute_targeted_search():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Order of operations: 1. Today's Device Date -> 2. Yesterday's Date
    search_dates = [
        datetime.date.today(),
        datetime.date.today() - datetime.timedelta(days=1)
    ]
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for d_obj in search_dates:
            target_path = d_obj.strftime("/%Y/%m/%d")
            # Look specifically for the link that matches the targeted date
            link = soup.find('a', href=lambda x: x and target_path in x)
            
            if link:
                # Find the parent article containing this specific date link
                article = link.find_parent('article')
                if article:
                    raw_content = article.get_text(separator="\n", strip=True)
                    lines = [line for line in raw_content.split('\n') if line.strip()]
                    
                    return {
                        "title": lines[0] if lines else "WOD",
                        "workout": "\n".join(lines[1:]) if len(lines) > 1 else "No movements.",
                        "hash": hashlib.sha256(raw_content.encode('utf-8')).hexdigest(),
                        "date_key": d_obj.strftime("%Y-%m-%d"),
                        "verified_path": target_path
                    }
    except Exception as e:
        st.sidebar.error(f"Search Failure: {e}")
    return None

# --- 2. THE UI & ARCHIVAL LAYER ---
st.title("TRI⚡DRIVE")
conn = st.connection("gsheets", type=GSheetsConnection)

# Execute Targeted Order
wod = execute_targeted_search()

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    # Visual Confirmation of the Search Order
    st.sidebar.success(f"Locked Target: {wod['verified_path']}")
    st.sidebar.info(f"Integrity Seal: {wod['hash'][:8]}")
else:
    st.error("No valid workout found for today or yesterday's targeted dates.")
    
