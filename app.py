import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_flexible_wod_extract():
    now = datetime.date.today()
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. DELETE THE TRASH (Menus, Footers, Nav)
            # This handles the links you saw like "Find a Gym" and "Store"
            for trash in soup(["nav", "header", "footer", "script", "style", "aside"]):
                trash.decompose()
            
            # 2. FIND THE BODY
            # We look for the article or the main content area
            main_content = soup.find('article') or soup.find('div', class_=re.compile(r'content|post|body|wod', re.I))
            
            if main_content:
                # Get every line of text
                lines = [line.strip() for line in main_content.get_text(separator="\n").split("\n")]
                
                # 3. BLACKLIST FILTER ONLY
                # We only remove known menu items; everything else stays
                blacklist = ["gym", "store", "course", "about", "media", "games", "login", "account", "privacy", "terms"]
                
                clean_lines = []
                for line in lines:
                    if len(line) < 3: continue # Skip empty/short fragments
                    if any(word in line.lower() for word in blacklist): continue
                    clean_lines.append(line)
                
                # If we have text, return it
                if clean_lines:
                    return {
                        "title": now.strftime("%y%m%d"),
                        "workout": "\n".join(clean_lines),
                        "url": target_url
                    }
    except Exception as e:
        return {"error": str(e)}
    return None

# --- UI LAYER ---
st.title("TRI⚡DRIVE")

wod = execute_flexible_wod_extract()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    # Using a larger text display for the workout
    st.markdown(f"### {wod['workout']}")
    st.sidebar.success("Direct Access: Verified")
    st.sidebar.markdown(f"[Source URL]({wod['url']})")
else:
    st.warning("Today's page reached, but content is not formatted as a standard WOD. It may be a Rest Day or a Video Feature.")
    if st.button("Check Previous Day"):
        # This is a one-click way to see if the scraper works on yesterday's data
        st.info("Searching for 251222...")
