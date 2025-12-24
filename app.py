import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json

def execute_final_content_harvest():
    homepage_url = "https://www.crossfit.com"
    # We use a more aggressive 'Bot' header to force the server to send pre-rendered HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        # 1. DISCOVERY VIA HOMEPAGE (STILL THE MOST RELIABLE)
        home_res = requests.get(homepage_url, headers=headers, timeout=10)
        home_soup = BeautifulSoup(home_res.text, 'html.parser')
        
        links = home_soup.find_all('a', href=True)
        target_path = next((l['href'] for l in links if re.search(r'/(\d{6})$', l['href'])), None)

        if not target_path:
            return {"error": "Could not find latest WOD ID on the homepage."}

        full_url = f"https://www.crossfit.com{target_path}" if target_path.startswith('/') else target_path

        # 2. TARGET THE FINAL RENDERED CONTENT
        page_res = requests.get(full_url, headers=headers, timeout=15)
        page_res.encoding = 'utf-8'
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        
        # A. Attempt: Standard Article Harvest (Worked in 1000003064.png)
        content_container = page_soup.find('article') or page_soup.find('main')
        
        # B. Fallback: Search for 'Hidden' Final Content (The JSON Data Shell)
        # Often modern sites store the 'final output' in a script tag to be fast
        if not content_container or len(content_container.get_text()) < 100:
            data_script = page_soup.find('script', string=re.compile("WOD|workout|title"))
            if data_script:
                # This pulls the 'Data' the website uses to fill the page
                return {"content": data_script.string, "url": full_url, "id": target_path}

        if content_container:
            return {
                "content": content_container.get_text(separator="\n", strip=True),
                "url": full_url,
                "id": target_path.split('/')[-1]
            }
            
    except Exception as e:
        return {"error": f"Final Content Error: {str(e)}"}
    return None

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE: FINAL CONTENT")

wod = execute_final_content_harvest()

if wod and "content" in wod:
    st.subheader(f"WOD ID: {wod.get('id', 'Unknown')}")
    # Displaying the final output without caring about the 'process'
    st.text(wod['content'].replace('♂', '(M)').replace('♀', '(F)'))
    st.sidebar.success("Target: Final Rendered Output")
    st.sidebar.markdown(f"[Source Page]({wod['url']})")
else:
    st.error("Problem Solver: Final content was not found in the HTML shell.")
    
