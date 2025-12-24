import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime

def execute_deep_discovery_harvest():
    # 1. ATTEMPT DYNAMIC DISCOVERY
    homepage_url = "https://www.crossfit.com"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    latest_id = None
    
    try:
        home_res = requests.get(homepage_url, headers=headers, timeout=10)
        home_soup = BeautifulSoup(home_res.text, 'html.parser')
        
        # AGGRESSIVE SEARCH: Look for any link containing 6 digits in a row
        all_links = home_soup.find_all(['a', 'link'], href=True)
        for a in all_links:
            href = a['href']
            # Pattern: Look for 6 digits (YYMMDD) anywhere in the URL path
            match = re.search(r'(\d{6})', href)
            if match:
                potential_id = match.group(1)
                # Basic validation: ensure it's not a year like 202500
                if potential_id.startswith('2'):
                    latest_id = potential_id
                    break

        # 2. FALLBACK: If homepage discovery fails, use the 'Current Date' ID
        if not latest_id:
            latest_id = datetime.date.today().strftime("%y%m%d")

        # 3. EXTRACTION: Navigate to the ID page
        target_url = f"https://www.crossfit.com/{latest_id}"
        page_res = requests.get(target_url, headers=headers, timeout=15)
        page_res.encoding = 'utf-8'
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        
        # Target the JSON Brain first (Next.js Data Shell)
        next_data = page_soup.find('script', id='__NEXT_DATA__')
        if next_data:
            data = json.loads(next_data.string)
            wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
            if wod_data:
                return {
                    "title": wod_data.get('title', f"WOD {latest_id}"),
                    "content": f"{wod_data.get('main_text', '')}\n\n{wod_data.get('stimulus', '')}",
                    "url": target_url
                }

        # Last Resort: Greedy Article Harvest
        article = page_soup.find('article') or page_soup.find('main')
        if article:
            return {"title": f"WOD {latest_id}", "content": article.get_text(separator="\n", strip=True), "url": target_url}

    except Exception as e:
        return {"error": str(e)}
    return {"error": "Could not identify content on homepage or direct date-URL."}

# --- UI LAYER ---
st.title("TRI⚡DRIVE")

wod = execute_deep_discovery_harvest()

if "content" in wod:
    st.subheader(wod['title'])
    st.info(wod['content'].replace('♂', '(M)').replace('♀', '(F)'))
    st.sidebar.success("Discovery: Deep Scan Active")
else:
    st.error(f"Logic Failure: {wod.get('error')}")
