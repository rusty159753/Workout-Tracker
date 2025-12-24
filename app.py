import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
import re

# --- THE SEARCH & RESCUE ENGINE ---
def execute_pattern_match_scrape():
    rss_url = "https://www.crossfit.com/feed"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) Safari/604.1"}
    
    # 2-Day Rolling Window (Today: 251223, Yesterday: 251222)
    today = datetime.date.today()
    target_dates = [today.strftime("%y%m%d"), (today - datetime.timedelta(days=1)).strftime("%y%m%d")]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        raw_text = response.text  # Get the raw string to bypass XML parsing errors
        
        for date_id in target_dates:
            # 1. THE SEARCH DOG: Find the date string and grab the nearest link
            # This regex looks for the date followed by a link or guid tag
            pattern = rf"<item>.*?{date_id}.*?<(?:link|guid).*?>(.*?)</(?:link|guid)>"
            match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
            
            if match:
                # Clean the found URL of any CDATA or XML leftovers
                target_link = match.group(1).strip()
                target_link = re.sub(r'<!\[CDATA\[|\]\]>|<.*?>', '', target_link)
                
                if "http" in target_link:
                    # 2. THE HYDRATION: Scrape the actual website for full content
                    res = requests.get(target_link, headers=headers, timeout=15)
                    page_soup = BeautifulSoup(res.content, 'html.parser')
                    
                    # Look for the workout content using semantic fallbacks
                    content = (
                        page_soup.find('article') or 
                        page_soup.find('div', class_=re.compile(r'content|post|entry|wod', re.I))
                    )
                    
                    if content:
                        full_text = content.get_text(separator="\n", strip=True)
                        return {
                            "title": date_id,
                            "workout": full_text,
                            "url": target_link,
                            "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest()
                        }
        
        # If nothing found, return a debug snippet for the sidebar
        return {"debug_raw": raw_text[:500]}
        
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

wod_result = execute_pattern_match_scrape()

if isinstance(wod_result, dict) and "workout" in wod_result:
    st.subheader(f"WOD: {wod_result['title']}")
    st.code(wod_result['workout'], language=None)
    st.sidebar.success("Status: Pattern Match Success")
    st.sidebar.markdown(f"[Source URL]({wod_result['url']})")
    st.sidebar.info(f"Integrity: {wod_result['hash'][:12]}")
else:
    st.error("Verified 2025 WOD not found in raw stream.")
    if "debug_raw" in wod_result:
        with st.expander("Diagnostic Telemetry"):
            st.write("Raw Feed Sample (First 500 chars):")
            st.text(wod_result["debug_raw"])
    if st.button("Force Deep Sync"):
        st.rerun()
        
