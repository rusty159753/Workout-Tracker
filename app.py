import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

def execute_final_no_fail_scrape():
    rss_url = "https://www.crossfit.com/feed"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)"}
    
    target_dates = [
        datetime.date.today().strftime("%y%m%d"),
        (datetime.date.today() - datetime.timedelta(days=1)).strftime("%y%m%d")
    ]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        # FIX: Using 'html.parser' instead of 'xml'. 
        # It is built-in to Python, requires no extra install, and is fault-tolerant.
        soup = BeautifulSoup(response.text, 'html.parser') 
        
        items = soup.find_all('item')
        for date_id in target_dates:
            for item in items:
                # In html.parser, tags are accessed the same way
                category = item.find('category').text if item.find('category') else ""
                title = item.find('title').text if item.find('title') else ""
                
                if "workout" in category.lower() and date_id in title:
                    target_link = item.find('link').next_sibling.strip() if item.find('link') else ""
                    # Fallback for link extraction in HTML mode
                    if not target_link or "http" not in target_link:
                        target_link = item.find('link').text

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
    except Exception as e:
        st.sidebar.error(f"Final Fail-Safe Error: {e}")
    return None

# --- UI ---
st.title("TRI⚡DRIVE")
wod = execute_final_no_fail_scrape()

if wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success("System: Online & Resilient")
else:
    st.error("Verified 2025 WOD not found. System is searching...")
    
