import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

def execute_audited_rss_scrape():
    rss_url = "https://www.crossfit.com/feed"
    # Hardened Headers for "Livelihood" Reliability
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    # 2-Day Rolling Window for Timezone Safety
    target_dates = [
        datetime.date.today().strftime("%y%m%d"),
        (datetime.date.today() - datetime.timedelta(days=1)).strftime("%y%m%d")
    ]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        root = ET.fromstring(response.content)
        
        for date_id in target_dates:
            for item in root.findall('.//item'):
                category = item.find('category').text if item.find('category') is not None else ""
                title = item.find('title').text if item.find('title') is not None else ""
                
                # 1. CATEGORY FILTER (Per prescription)
                if "workout" in category.lower():
                    # 2. DATE ID MATCH (Current Year/Date)
                    if date_id in title:
                        link = item.find('link').text
                        # 3. HYDRATION (Full Page Scrape)
                        res = requests.get(link, headers=headers, timeout=15)
                        soup = BeautifulSoup(res.content, 'html.parser')
                        article = soup.find('article')
                        
                        if article:
                            full_text = article.get_text(separator="\n", strip=True)
                            return {
                                "title": title,
                                "workout": full_text,
                                "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest(),
                                "url": link
                            }
    except Exception as e:
        st.sidebar.error(f"Audit Integrity Failure: {e}")
    return None

# --- UI LAYER ---
st.title("TRI⚡DRIVE")
wod = execute_audited_rss_scrape()

if wod:
    st.subheader(f"WOD: {wod['title']}")
    # Using 'code' block to preserve the specific formatting of movement lists
    st.code(wod['workout'], language=None)
    st.sidebar.success(f"Category Verified: Workout of the Day")
    st.sidebar.info(f"Integrity Hash: {wod['hash'][:10]}")
else:
    st.error("Verified 2025 WOD not found in current feed window.")
                
