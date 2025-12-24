import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_boundary_validated_scrape():
    now = datetime.date.today()
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. REMOVE GLOBAL SITE NOISE
            for noise in soup(["nav", "footer", "header", "script", "style"]):
                noise.decompose()

            # 2. DEFINE OUR BOUNDARY MARKERS
            # Today's date (251223) and the universal CTA
            date_anchor = now.strftime("%y%m%d")
            cta_pattern = r"Post\s+.*?\s+to\s+comments"
            
            # Get the full text stream of the page
            page_text = soup.get_text(separator="\n", strip=True)
            
            # 3. BOUNDARY LOCKING
            # Find where the date appears (The Start)
            start_idx = page_text.find(date_anchor)
            
            if start_idx != -1:
                # Find the CTA after the date (The End)
                cta_match = re.search(cta_pattern, page_text[start_idx:], re.IGNORECASE)
                
                if cta_match:
                    # Calculate end position relative to the start_idx
                    end_idx = start_idx + cta_match.end()
                    
                    # EXTRACT THE VALIDATED WORKOUT
                    raw_wod = page_text[start_idx:end_idx].strip()
                    
                    # Final cleanup of any stray menu fragments that snuck in
                    clean_wod = re.sub(r'Log In|Create an account|View Profile', '', raw_wod)
                    
                    return {
                        "workout": clean_wod,
                        "url": target_url,
                        "validated": True
                    }
        
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.title("TRI⚡DRIVE")

wod = execute_boundary_validated_scrape()

if wod and "workout" in wod:
    st.subheader(f"WOD {datetime.date.today().strftime('%y%m%d')}")
    # Display the validated block
    st.info(wod['workout'])
    st.sidebar.success("Validators: Date & CTA Matched")
else:
    st.error("Boundary Failure: Date or 'Post to comments' CTA not found on page.")
    
