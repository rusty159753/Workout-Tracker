import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_surgical_wod_extract():
    # Target today's URL directly via Googlebot spoofing
    now = datetime.date.today()
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. KILL NOISE AT THE SOURCE
            # Deleting these tags removes the menu links shown in your screenshot
            for noise in soup(["nav", "header", "footer", "script", "style", "aside"]):
                noise.decompose()
            
            # 2. TARGET THE MAIN BODY
            main_body = soup.find('div', class_='col-sm-12') or soup.find('article')
            
            if main_body:
                raw_text = main_body.get_text(separator="\n").split("\n")
                
                # 3. KEYWORD DENSITY FILTERING
                # Blacklist: If these words are in the line, discard it (Kills the menu)
                blacklist = ["gym", "store", "course", "about", "media", "games", "login", "account"]
                # Whitelist: If it has these, it's likely part of the WOD (Protects Isabel)
                whitelist = ["reps", "rounds", "time", "lb", "kg", "rx", "amrap", "emom", "set"]
                
                clean_lines = []
                for line in raw_text:
                    clean_line = line.strip()
                    low_line = clean_line.lower()
                    
                    # Logic: Discard if in blacklist; Keep if it has numbers or whitelist keywords
                    if any(word in low_line for word in blacklist):
                        continue
                    if any(word in low_line for word in whitelist) or any(char.isdigit() for char in clean_line):
                        if len(clean_line) > 2: # Ignore stray characters
                            clean_lines.append(clean_line)
                
                return {
                    "title": now.strftime("%y%m%d"),
                    "workout": "\n".join(clean_lines),
                    "url": target_url
                }
    except Exception as e:
        return {"error": str(e)}
    return None

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

with st.spinner("Isolating Workout Data..."):
    wod = execute_surgical_wod_extract()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    # Using 'st.markdown' here can help handle formatting better than st.code
    st.markdown(f"**{wod['workout']}**") 
    st.sidebar.success("Surgical Extraction: Active")
    st.sidebar.markdown(f"[Source URL]({wod['url']})")
else:
    st.error("WOD isolated, but no workout movements detected. Feed may be a 'Rest Day'.")
    if st.button("Deep Refresh"):
        st.rerun()
        
