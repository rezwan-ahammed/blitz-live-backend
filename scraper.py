import os
import json
import requests
from google import genai
from google.genai import types

# ১. জেমিনি ক্লায়েন্ট সেটআপ
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is missing!")

client = genai.Client(api_key=api_key)

def fetch_iptv_links():
    try:
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        # কিছু পপুলার স্পোর্টস আইডি
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us']
        streams = [s for s in data if s.get('channel') in target_ids]
        return str(streams[:10])
    except:
        return "[]"

def generate_smart_json(iptv_data):
    prompt = f"""
    Analyze these streams and create a 'Hero Card' JSON for 'Blitz Live' app.
    Today is March 17, 2026. Use Google Search to find any LIVE cricket or football match happening now.
    Match the match title with the best stream from this data: {iptv_data}
    
    IMPORTANT: Output ONLY pure JSON. NO markdown blocks (```), NO backticks, NO talk.
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
        # টুলটির নাম সংশোধন করা হয়েছে (GoogleSearchRetrieval -> GoogleSearch)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"DEBUG: AI Call Failed: {str(e)}")
        return ""

if __name__ == "__main__":
    print("🚀 Blitz Live Backend Starting...")
    raw = fetch_iptv_links()
    ai_output = generate_smart_json(raw)
    
    if not ai_output:
        print("❌ AI returned empty response.")
        ai_output = "{}"

    try:
        # জেসন ক্লিন করার প্রো-লজিক
        clean_json = ai_output
        if "{" in clean_json:
            clean_json = clean_json[clean_json.find("{"):clean_json.rfind("}")+1]
        
        json_obj = json.loads(clean_json)
        
        # যদি হিরো কার্ডের ভেতরে টাইটেল না থাকে, তবে ফেইল-সেফ ডাটা সেট করা
        if 'hero_match' not in json_obj:
            raise ValueError("Invalid structure")

        with open("live.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(json_obj, indent=2))
        print(f"✅ SUCCESS: Match found -> {json_obj['hero_match']['title']}")
        
    except Exception as e:
        print(f"❌ JSON Parse Error: {str(e)}")
        # ফেইল-সেফ ডাটা (যাতে অ্যাপ না ভাঙ্গে)
        fallback = {
            "hero_match": {
                "title": "Searching for Live Matches...",
                "status": "Check Back Soon",
                "stream_url": "",
                "user_agent": "Default",
                "referer": "Default"
            }
        }
        with open("live.json", "w") as f:
            f.write(json.dumps(fallback))
