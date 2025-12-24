import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
import re

def execute_final_publish_scrape():
    rss_url = "https://www.crossfit.com/feed"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)"}
    
    # Target IDs: 251223 and 251222
    today = datetime.date.today()
    target_dates = [today.strftime("%y%m%d"), (today - datetime.timedelta(days=1)).strftime("%y%m%d")]
    
    found_items_for_debug = []

    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser') 
        items = soup.find_all('item')
        
        for item in items:
            title = item.find('title').get_text(strip=True) if item.find('title') else "No Title"
            category = item.find('category').get_text(strip=True).lower() if item.find('category') else "No Category"
            found_items_for_debug.append(f"T: {title} | C: {category}")

            # NEW LOGIC: Any item with the date ID in the title is likely our WOD
            for date_id in target_dates:
                if date_id in title:
                    # Found a date match! Now get the link.
                    link_tag = item.find('guid') or item.find('link')
                    target_link = link_tag.get_text(strip=True) if link_tag else ""
                    
                    if "http" in target_link:
                        res = requests.get(target_link, headers=headers, timeout=15)
                        page_soup = BeautifulSoup(res.content, 'html.parser')
                        
                        # Content recovery
                        content = page_soup.find('article') or page_soup.find('div', class_=re.compile(r'content|post|entry|wod', re.I))
                        
                        if content:
                            full_text = content.get_text(separator="\n", strip=True)
                            return {
                                "title": title,
                                "workout": full_text,
                                "url": target_link,
                                "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest()
                            }
    except Exception as e:
        st.error(f"Critical System Error: {e}")
    
    return {"debug": found_items_for_debug}

# --- UI ---
st.title("TRI⚡DRIVE")
wod = execute_final_publish_scrape()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success("Found: 2025 Validated Content")
else:
    st.error("Verified 2025 WOD not found in current feed.")
    with st.expander("Technical Debugging Info"):
        st.write("Last 10 items found in feed:")
        for entry in wod.get("debug", [])[:10]:
            st.write(entry)
                
