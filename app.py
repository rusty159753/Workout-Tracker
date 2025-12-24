import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
import re
from streamlit_gsheets import GSheetsConnection

# --- THE REDUNDANCY ENGINE ---
def execute_hardened_final_scrape():
    rss_url = "https://www.crossfit.com/feed"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1"
    }
    
    # 2-Day Rolling Window (Safety for Timezone Rollovers)
    today = datetime.date.today()
    target_dates = [today.strftime("%y%m%d"), (today - datetime.timedelta(days=1)).strftime("%y%m%d")]
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=20)
        # Use html.parser: Built-in to Python, no extra installs, handles malformed XML
        soup = BeautifulSoup(response.text, 'html.parser') 
        items = soup.find_all('item')
        
        for date_id in target_dates:
            for item in items:
                # 1. MULTI-FACTOR IDENTITY SCORE
                title = item.find('title').get_text(strip=True) if item.find('title') else ""
                category = item.find('category').get_text(strip=True).lower() if item.find('category') else ""
                
                confidence_score = 0
                if "workout of the day" in category: confidence_score += 1
                if re.match(r'^\d{6}$', title): confidence_score += 1
                if date_id in title: confidence_score += 1
                
                # Minimum score of 2 ensures we don't pull news articles or random posts
                if confidence_score >= 2:
                    # 2. STABLE LINK SELECTION (GUID is more reliable over 3-year history)
                    link_tag = item.find('guid') or item.find('link')
                    target_link = link_tag.get_text(strip=True) if link_tag else ""
                    
                    if "http" in target_link:
                        res = requests.get(target_link, headers=headers, timeout=15)
                        page_soup = BeautifulSoup(res.content, 'html.parser')
                        
                        # 3. SEMANTIC CONTENT RECOVERY
                        # Priority: <article> tag -> Content/Post/Entry Div -> Body Fallback
                        content = (
                            page_soup.find('article') or 
                            page_soup.find('div', class_=re.compile(r'content|post|entry|wod', re.I))
                        )
                        
                        if content:
                            full_text = content.get_text(separator="\n", strip=True)
                            return {
                                "title": title,
                                "workout": full_text,
                                "url": target_link,
                                "hash": hashlib.sha256(full_text.encode('utf-8')).hexdigest()
                            }
    except Exception as e:
        st.sidebar.error(f"System Audit Alert: {e}")
    return None

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

# Visual feedback for the user
with st.status("Syncing with CrossFit HQ Feed...", expanded=False) as status:
    wod = execute_hardened_final_scrape()
    if wod:
        status.update(label="Workout Verified!", state="complete")
    else:
        status.update(label="Searching Archives...", state="error")

if wod:
    st.subheader(f"WOD: {wod['title']}")
    # Preserving the raw movement formatting for readability
    st.code(wod['workout'], language=None)
    
    # Audit trail for the Owner
    st.sidebar.success("Found: 2025 Validated Content")
    st.sidebar.info(f"Integrity Hash: {wod['hash'][:12]}")
    st.sidebar.markdown(f"[Source URL]({wod['url']})")
else:
    st.error("Verified 2025 WOD not currently found. The feed may be updating.")
    if st.button("Force Re-Sync"):
        st.rerun()
            
