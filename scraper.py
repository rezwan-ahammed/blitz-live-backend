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
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us']
        streams = [s for s in data if s.get('channel') in target_ids]
        return str(streams[:10])
    except:
        return "[]"

def generate_smart_json(iptv_data):
    # এআই-কে খুব কড়া ভাষায় ইনস্ট্রাকশন দিচ্ছি
    prompt = f"""
    You are the 'Blitz Live' backend engine. 
    1. SEARCH Google for any LIVE cricket or football match happening RIGHT NOW (March 17, 2026).
    2. Pick the most relevant m3u8 stream from this data: {iptv_data}
    3. Output ONLY valid JSON for our app.
    
    Structure:
    {{
      "hero_match": {{
        "title": "Exact Match Name",
        "status": "LIVE NOW",
        "stream_url": "url from data",
        "user_agent": "Default",
        "referer": "Default"
      }}
    }}
    
    CRITICAL: Output ONLY the JSON. No markdown, no backticks, no text before or after.
    """
    
    try:
        # ২০২৬ গুগলে সার্চ টুলের লেটেস্ট সিনট্যাক্স
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"DEBUG AI CALL ERROR: {str(e)}")
        return ""

if __name__ == "__main__":
    print("🚀 Blitz Live Engine Starting...")
    raw = fetch_iptv_links()
    ai_output = generate_smart_json(raw)
    
    # ডিবানিং এর জন্য এআই এর কাঁচা উত্তর প্রিন্ট করা হচ্ছে
    print(f"--- AI RAW OUTPUT ---\n{ai_output}\n---------------------")

    try:
        # জেসন ক্লিন করার আলটিমেট লজিক
        clean_json = ai_output
        if "{" in clean_json:
            clean_json = clean_json[clean_json.find("{"):clean_json.rfind("}")+1]
        
        json_obj = json.loads(clean_json)
        
        if 'hero_match' not in json_obj:
            raise ValueError("Structure mismatch")

        with open("live.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(json_obj, indent=2))
        print(f"✅ SUCCESS: {json_obj['hero_match']['title']} is now LIVE!")
        
    except Exception as e:
        print(f"❌ PARSE ERROR: {str(e)}")
        # ফেইল-সেফ ডাটা (যাতে অ্যাপ না ভাঙ্গে)
        fallback = {
            "hero_match": {
                "title": "Match Loading...",
                "status": "Refreshing Every 3 Hours",
                "stream_url": "",
                "user_agent": "Default",
                "referer": "Default"
            }
        }
        with open("live.json", "w") as f:
            f.write(json.dumps(fallback))
