import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
import re

def execute_final_raw_sync():
    rss_url = "https://www.crossfit.com/feed"
    # RESET HEADERS: Use a basic bot header to prevent the Homepage Redirect
    headers = {"User-Agent": "WOD-Scraper/1.0"}
    
    today = datetime.date.today()
    target_dates = [today.strftime("%y%m%d"), (today - datetime.timedelta(days=1)).strftime("%y%m%d")]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        # Verify if we actually got XML or still got HTML
        is_html = response.text.strip().startswith("<!DOCTYPE html")
        
        for date_id in target_dates:
            # BROAD PATTERN MATCH: Find the date and the very next URL
            # This works whether it's an RSS <link> or an HTML <a> tag
            pattern = rf"{date_id}.*?(https?://www\.crossfit\.com/[^\s\"<>]+)"
            match = re.search(pattern, response.text, re.DOTALL | re.IGNORECASE)
            
            if match:
                target_link = match.group(1).strip()
                # Clean up trailing characters
                target_link = target_link.split('<')[0].split('"')[0].split(']')[0]
                
                if "http" in target_link:
                    res = requests.get(target_link, headers=headers, timeout=15)
                    page_soup = BeautifulSoup(res.content, 'html.parser')
                    content = page_soup.find('article') or page_soup.find('div', class_=re.compile(r'content|post|entry', re.I))
                    
                    if content:
                        full_text = content.get_text(separator="\n", strip=True)
                        return {
                            "title": date_id,
                            "workout": full_text,
                            "url": target_link,
                            "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest(),
                            "type": "HTML" if is_html else "XML"
                        }
        
        return {"debug": response.text[:1000]} # Send more text for debugging
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
st.title("TRI⚡DRIVE")
wod = execute_final_raw_sync()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success(f"Source Type: {wod['type']}")
    st.sidebar.markdown(f"[Source URL]({wod['url']})")
else:
    st.error("Target data not found in the current stream.")
    if "debug" in wod:
        with st.expander("Diagnostic Telemetry"):
            st.text(wod["debug"])
        
