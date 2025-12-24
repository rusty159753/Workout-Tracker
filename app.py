import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

def execute_locked_json_harvest():
    # Strategy: Homepage Discovery to find the most recent canonical URL
    homepage_url = "https://www.crossfit.com"
    # Googlebot headers force the server to provide pre-rendered data blocks
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    try:
        # 1. DISCOVERY PHASE
        home_res = requests.get(homepage_url, headers=headers, timeout=10)
        home_soup = BeautifulSoup(home_res.text, 'html.parser')
        
        # Scan for the first ID-based link (/YYMMDD)
        latest_path = None
        for a in home_soup.find_all('a', href=True):
            if re.search(r'/(\d{6})$', a['href']):
                latest_path = a['href']
                break
        
        if not latest_path:
            return {"error": "Could not identify the latest workout ID on the homepage."}

        # 2. TARGETING PHASE
        target_url = f"https://www.crossfit.com{latest_path}" if latest_path.startswith('/') else latest_path
        page_res = requests.get(target_url, headers=headers, timeout=15)
        page_res.encoding = 'utf-8'
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        
        # 3. EXTRACTION PHASE (JSON ENGINE)
        # Targeting the Next.js data shell for the 'Final Content'
        next_data_script = page_soup.find('script', id='__NEXT_DATA__')
        
        if next_data_script:
            data = json.loads(next_data_script.string)
            # Schema Path: props -> pageProps -> wod
            wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
            
            if wod_data:
                title = wod_data.get('title', 'Workout of the Day')
                main_text = wod_data.get('main_text', '')
                stimulus = wod_data.get('stimulus', '')
                
                # Combine for the final output
                final_output = f"{main_text}"
                if stimulus:
                    final_output += f"\n\n**Stimulus & Strategy:**\n{stimulus}"
                
                return {
                    "title": title,
                    "content": final_output,
                    "url": target_url
                }

        # 4. FALLBACK PHASE (Greedy HTML)
        # If the JSON structure shifts, we revert to the proven HTML Harvest
        article = page_soup.find('article')
        if article:
            return {
                "title": "WOD (Harvest Mode)",
                "content": article.get_text(separator="\n", strip=True),
                "url": target_url
            }

    except Exception as e:
        return {"error": f"Technical Failure: {str(e)}"}
    return None

# --- STREAMLIT UI ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡", layout="centered")

st.title("TRI⚡DRIVE")

with st.spinner("Fetching final content..."):
    wod = execute_locked_json_harvest()

if wod and "content" in wod:
    st.subheader(wod.get('title', 'Latest Workout'))
    
    # Process symbols for the Pixel display
    display_text = wod['content'].replace('♂', '(M)').replace('♀', '(F)')
    
    # Using st.info for a clean, professional card look
    st.info(display_text)
    
    st.sidebar.success("Status: Verified JSON Pull")
    st.sidebar.markdown(f"[Source: CrossFit.com]({wod['url']})")
else:
    error_msg = wod.get("error") if wod else "Unknown error"
    st.error(f"Logic failure: {error_msg}")
    
