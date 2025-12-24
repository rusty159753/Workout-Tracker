import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

def execute_live_mirror_harvest():
    # 1. DISCOVERY: Find exactly what CrossFit.com is showing right now
    homepage_url = "https://www.crossfit.com"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    try:
        # Get the homepage source
        home_res = requests.get(homepage_url, headers=headers, timeout=10)
        home_soup = BeautifulSoup(home_res.text, 'html.parser')
        
        # Identify the FIRST workout ID link on the page
        latest_path = None
        for a in home_soup.find_all('a', href=True):
            # Look for the 6-digit ID pattern anywhere in the link
            match = re.search(r'(\d{6})', a['href'])
            if match:
                latest_path = a['href']
                break
        
        if not latest_path:
            return {"error": "Could not identify the live workout on the homepage."}

        # 2. TARGETING: Navigate to that live URL
        target_url = f"https://www.crossfit.com{latest_path}" if latest_path.startswith('/') else latest_path
        page_res = requests.get(target_url, headers=headers, timeout=15)
        page_res.encoding = 'utf-8'
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        
        # 3. EXTRACTION: Pull the JSON 'Brain' (Final Content)
        next_data = page_soup.find('script', id='__NEXT_DATA__')
        if next_data:
            data = json.loads(next_data.string)
            wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
            
            if wod_data:
                return {
                    "title": wod_data.get('title', 'Workout of the Day'),
                    "main": wod_data.get('main_text', ''),
                    "stimulus": wod_data.get('stimulus', ''),
                    "url": target_url,
                    "id": re.search(r'(\d{6})', target_url).group(1)
                }

        # FALLBACK: If JSON fails, harvest the Article text
        article = page_soup.find('article') or page_soup.find('main')
        if article:
            return {
                "title": "WOD (Live Harvest)",
                "main": article.get_text(separator="\n", strip=True),
                "url": target_url,
                "id": "Live"
            }

    except Exception as e:
        return {"error": str(e)}
    return {"error": "Could not sync with the live homepage."}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

with st.spinner("Syncing with live CrossFit.com feed..."):
    wod = execute_live_mirror_harvest()

if wod and "main" in wod:
    # Display the current live WOD
    st.subheader(wod['title'])
    
    # Symbols cleaned for the Pixel display
    clean_main = wod['main'].replace('♂', '(M)').replace('♀', '(F)')
    st.info(clean_main)
    
    if wod.get('stimulus'):
        with st.expander("Stimulus & Strategy"):
            st.write(wod['stimulus'].replace('♂', '(M)').replace('♀', '(F)'))
            
    st.sidebar.success(f"Live Sync: /{wod.get('id', 'Found')}")
    st.sidebar.markdown(f"[Source Page]({wod['url']})")
else:
    st.error(f"Sync Failure: {wod.get('error')}")
