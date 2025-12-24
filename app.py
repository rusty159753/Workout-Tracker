import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. THE HARDENED RSS-HYDRATION ENGINE ---
def execute_hardened_rss_scrape():
    rss_url = "https://www.crossfit.com/feed"
    # Mobile browser headers to ensure we aren't blocked by bot filters
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1"
    }
    
    # 2-Day Rolling Window for Timezone/Publishing Safety
    target_dates = [
        datetime.date.today().strftime("%y%m%d"), # Today: 251223
        (datetime.date.today() - datetime.timedelta(days=1)).strftime("%y%m%d") # Yesterday: 251222
    ]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        # FIX: BeautifulSoup uses a fault-tolerant parser that ignores "Invalid Tokens" 
        # like the one found at column 1293.
        soup = BeautifulSoup(response.text, 'xml') 
        
        items = soup.find_all('item')
        for date_id in target_dates:
            for item in items:
                category = item.find('category').text if item.find('category') else ""
                title = item.find('title').text if item.find('title') else ""
                
                # PRESCRIBED FILTERS: Strictly Workout Category + Correct Date ID
                if "workout" in category.lower() and date_id in title:
                    target_link = item.find('link').text
                    
                    # HYDRATION: Visit the full URL to get Stimulus/Scaling missing from RSS
                    res = requests.get(target_link, headers=headers, timeout=15)
                    page_soup = BeautifulSoup(res.content, 'html.parser')
                    article = page_soup.find('article')
                    
                    if article:
                        full_text = article.get_text(separator="\n", strip=True)
                        return {
                            "title": title,
                            "workout": full_text,
                            "url": target_link,
                            "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest()
                        }
        return None
    except Exception as e:
        st.sidebar.error(f"Scrape Integrity Failed: {e}")
        return None

# --- 2. THE UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

# Initialize Connection (Ensure secrets.toml is set up for GSheets)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.sidebar.warning("GSheets connection pending setup.")

wod = execute_hardened_rss_scrape()

if wod:
    st.subheader(f"WOD: {wod['title']}")
    # Using 'code' block to preserve movement formatting (AMRAP lists, etc.)
    st.code(wod['workout'], language=None)
    
    # Audit Sidebar
    st.sidebar.success("Status: Source Verified")
    st.sidebar.info(f"Integrity Hash: {wod['hash'][:12]}")
    st.sidebar.markdown(f"[View Source]({wod['url']})")
else:
    st.error("No verified 2025 WOD found. Check back after the next feed sync.")
    
