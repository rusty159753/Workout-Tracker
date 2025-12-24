import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime

def execute_flushed_out_scrape():
    now = datetime.date.today()
    # 1. GENERATE SEARCH WINDOW (Today then Yesterday)
    dates_to_check = [now, now - datetime.timedelta(days=1)]
    
    # Using Googlebot is non-negotiable for bypassing the HTML Wall
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    for target_date in dates_to_check:
        url = target_date.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
        try:
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code == 200:
                # 2. VISUAL ANCHOR EXTRACTION
                soup = BeautifulSoup(response.text, 'html.parser')
                # Clean out the 'noise' tags identified in previous failures
                for s in soup(["script", "style", "nav", "footer", "header"]):
                    s.decompose()
                
                page_text = soup.get_text(separator="\n", strip=True)
                
                # We target the exact anchors from your screenshot (1000003063.png)
                start_marker = "WORKOUT OF THE DAY"
                end_marker = "Scaling" # Or "Stimulus"
                
                start_idx = page_text.find(start_marker)
                if start_idx != -1:
                    end_idx = page_text.find(end_marker, start_idx)
                    # If end marker missing, grab the next 1200 characters
                    workout_text = page_text[start_idx:end_idx].strip() if end_idx != -1 else page_text[start_idx:start_idx+1200]
                    
                    return {
                        "date": target_date.strftime("%y%m%d"),
                        "workout": workout_text,
                        "url": url
                    }
        except Exception:
            continue # Move to the next date in the window if a crash occurs
            
    return None

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

# The status bar now reflects the 'Search Window' logic
with st.status("Syncing: Scanning 48-Hour WOD Window...", expanded=False) as status:
    wod = execute_flushed_out_scrape()
    if wod:
        status.update(label=f"WOD Found: {wod['date']}", state="complete")
    else:
        status.update(label="No WOD found in window.", state="error")

if wod:
    st.subheader(f"WOD {wod['date']}")
    # Using st.text preserves the '30 snatches' vertical layout
    st.text(wod['workout'])
    st.sidebar.success("Direct-Anchor Strategy: Active")
    st.sidebar.markdown(f"[Source Site]({wod['url']})")
else:
    st.error("Problem Solvers: Both Predictive and Backup paths have failed. Please check the 'Diagnostic Telemetry'.")
    
