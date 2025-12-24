import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_historical_best_logic():
    # 1. PREDICTIVE URL (SUCCESS FROM MID-CHAT)
    now = datetime.date.today()
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    
    # 2. GOOGLEBOT HEADERS (SUCCESS FROM FIRST BYPASS)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 3. GREEDY ARTICLE EXTRACTION (THE ONLY WAY WE SAW ISABEL)
            # We target the largest content container, then clean it.
            main_content = soup.find('article') or soup.find('main') or soup.find('div', id='main-content')
            
            if main_content:
                # 4. BLACKLIST CLEANING (LEARNED FROM THE NAVIGATION JUNK FAILURE)
                for junk in main_content(["nav", "header", "footer", "aside", "ul", "li", "script", "style"]):
                    junk.decompose()
                
                # Extract text with preserved spacing
                lines = main_content.get_text(separator="\n", strip=True).split("\n")
                
                # 5. DENSITY FILTER (LEARNED FROM THE 'REST DAY' ERROR)
                # We keep lines that are descriptive or have workout data.
                final_lines = []
                blacklist_keywords = ["gym", "store", "about", "media", "games", "login", "privacy"]
                
                for line in lines:
                    low_line = line.lower().strip()
                    # Skip if it's too short or contains menu junk
                    if len(low_line) < 3 or any(word in low_line for word in blacklist_keywords):
                        continue
                    final_lines.append(line)
                
                if final_lines:
                    return {
                        "workout": "\n".join(final_lines),
                        "url": target_url
                    }
        return {"error": f"Server Response: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.title("TRI⚡DRIVE")

wod = execute_historical_best_logic()

if wod and "workout" in wod:
    st.subheader(f"WOD {datetime.date.today().strftime('%y%m%d')}")
    # Using st.info creates the 'clean card' look you wanted
    st.info(wod['workout'])
    st.sidebar.success("Historical Pattern: Active")
else:
    st.error("Problem Solver: Integrated Logic failed to isolate 'Isabel'.")
    
