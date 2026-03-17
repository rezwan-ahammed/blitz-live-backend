import os
import json
import requests
from google import genai

# ১. ২০২৬-এর নতুন Gemini API ক্লায়েন্ট সেটআপ
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is missing in GitHub Secrets!")

client = genai.Client(api_key=api_key)

def fetch_raw_sports_data():
    try:
        # iptv-org থেকে ডাটা কালেকশন
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        
        # কিছু পপুলার স্পোর্টস আইডি ফিল্টার
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us']
        sports_streams = [s for s in data if s.get('channel') in target_ids]
        
        if not sports_streams:
            sports_streams = data[:20] # ব্যাকআপ
            
        return str(sports_streams[:10])
    except Exception as e:
        return f"Fetch Error: {str(e)}"

def generate_blitz_json(raw_data):
    prompt = f"""
    You are the AI engine for 'Blitz Live' app. 
    Analyze these IPTV streams and create a perfect JSON for our Hero Card.
    If you see a sports channel, make up a cool match title like 'IPL 2026: Live Now' or 'BD vs IND Live'.
    
    Data: {raw_data}
    
    Format:
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW",
        "stream_url": "url",
        "user_agent": "Default",
        "referer": "Default"
      }}
    }}
    """
    
    try:
        # ২০২৬-এর জন্য সবচেয়ে ফাস্ট মডেল: gemini-2.0-flash
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        output = response.text.strip()
        
        # জেসন ক্লিন করা
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0].strip()
        return output
    except Exception as e:
        return f"AI Error: {str(e)}"

if __name__ == "__main__":
    print("Step 1: Fetching raw data...")
    raw = fetch_raw_sports_data()
    
    print("Step 2: Processing with AI (Gemini 2.0 Flash)...")
    final_json = generate_blitz_json(raw)
    
    try:
        # ভ্যালিডেশন
        json.loads(final_json)
        with open("live.json", "w", encoding="utf-8") as f:
            f.write(final_json)
        print("Success! live.json is ready for Rezwan's app.")
    except:
        # ফেইল সেফ মোড (যাতে অ্যাপ না ভাঙ্গে)
        print("AI output failed validation. Using default data.")
        default = '{"hero_match": {"title": "Live Sports Update", "status": "Streaming Soon", "stream_url": "", "user_agent": "Default", "referer": "Default"}}'
        with open("live.json", "w") as f:
            f.write(default)
