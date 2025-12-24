import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime

# --- UI & Mobile CSS Configuration ---
st.set_page_config(page_title="TriDrive Performance", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    /* PRESERVE-LAYOUT: Forces the browser to respect \n characters from the scrape */
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

def execute_structured_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Ensures ♀ and ♂ symbols render correctly
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Scoping the scrape to the main 'article' tag to isolate content
        article = soup.find('article')
        if not article: return None

        # separator="\n" preserves the vertical alignment of the weight requirements
        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        # Data containers and logic variables
        data = {"title": "Isabel", "workout_lines": [], "stimulus_lines": [], "scaling_lines": []}
        current_section = "HEAD" 

        for line in lines:
            # Transitions: Identifying headers to change the current_section variable
            if "Stimulus" in line:
                current_section = "STIMULUS"
                continue
            elif "Scaling" in line:
                current_section = "SCALING"
                continue
            elif any(stop in line for stop in ["Resources", "View results"]):
                break
            
            # Content Assignment based on current_section variable
            if current_section == "HEAD":
                # Capturing movements (e.g., 30 Snatches) and weight requirements
                if "Workout of the Day" not in line and not line.isdigit():
                    if any(s in line for s in ['♀', '♂']):
                        data["workout_lines"].append(f"**{line}**")
                    else:
                        data["workout_lines"].append(line)
            elif current_section == "STIMULUS":
                data["stimulus_lines"].append(line)
            elif current_section == "SCALING":
                data["scaling_lines"].append(line)

        return {
            "title": data["workout_lines"][0] if data["workout_lines"] else "Isabel",
            "workout": "\n".join(data["workout_lines"][1:]) if len(data["workout_lines"]) > 1 else "\n".join(data["workout_lines"]),
            "stimulus": "\n\n".join(data["stimulus_lines"]),
            "scaling": "\n\n".join(data["scaling_lines"])
        }
    except:
        return None

# --- UI Execution ---
st.title("TRI⚡DRIVE")
st.caption("Industrial Scrape Engine | Date: 2025.12.23")

if 'wod_data' not in st.session_state or st.sidebar.button("Refresh Scrape"):
    st.session_state.wod_data = execute_structured_scrape()

wod = st.session_state.wod_data

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    with st.expander("⚡ Stimulus and Strategy"):
        st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)
        
    with st.expander("⚖️ Scaling Options"):
        st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)
else:
    st.error("Connection error. Ensure Seattle VPN is active and use the Sidebar Refresh.")
            
