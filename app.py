import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime

def execute_total_page_harvest():
    # 1. LOCK ONTO THE VERIFIED ID-URL
    now = datetime.date.today()
    date_id = now.strftime("%y%m%d")
    target_url = f"https://www.crossfit.com/{date_id}"
    
    # Using Googlebot headers to ensure the server doesn't block the 'Harvest'
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. TARGET THE ENTIRE ARTICLE CONTAINER
            # We are pulling EVERYTHING inside the main content area
            article = soup.find('article') or soup.find('main')
            
            if article:
                # 3. NO-FILTER EXTRACTION
                # We use a newline separator to keep the list items (30 snatches) distinct
                raw_text_harvest = article.get_text(separator="\n", strip=True)
                
                return {
                    "harvest": raw_text_harvest,
                    "url": target_url
                }
            else:
                # If no article tag, harvest the entire body (last resort)
                return {
                    "harvest": soup.body.get_text(separator="\n", strip=True),
                    "url": target_url
                }
                
        return {"error": f"Failed to reach {target_url}. Status: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE: TOTAL HARVEST")

wod = execute_total_page_harvest()

if wod and "harvest" in wod:
    st.subheader(f"Raw Data Capture: {datetime.date.today().strftime('%y%m%d')}")
    # Using st.text to show exactly how the line breaks are appearing
    st.text(wod['harvest'])
    st.sidebar.info("Method: Total Article Harvest")
    st.sidebar.markdown(f"[Source URL]({wod['url']})")
else:
    st.error("Harvest Failed. The ID-based URL might be behind a redirect or a temporary block.")
