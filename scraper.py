import os
import json
import requests
from google import genai
from google.genai import types

# ১. জেমিনি ক্লায়েন্ট সেটআপ (নতুন এপিআই কি ব্যবহার হবে)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is missing in GitHub Secrets!")

client = genai.Client(api_key=api_key)

def fetch_iptv_links():
    """ইন্টারনেট থেকে সরাসরি আইপিটিভি চ্যানেলের কাঁচা ডাটা আনা"""
    try:
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        
        # পপুলার স্পোর্টস আইডি ফিল্টার
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us']
        streams = [s for s in data if s.get('channel') in target_ids]
        
        if not streams:
            streams = data[:15] # ব্যাকআপ
            
        return str(streams[:10])
    except Exception as e:
        print(f"Fetch Error: {str(e)}")
        return "[]"

def generate_smart_json(iptv_data):
    """গুগল সার্চ ব্যবহার করে আজকের লাইভ ম্যাচ খুঁজে বের করা"""
    prompt = f"""
    Context: Today is March 17, 2026. 
    Task: 
    1. Search Google for any LIVE cricket or football matches happening right now.
    2. Pick the best match and find a relevant stream from this data: {iptv_data}
    3. Output ONLY a valid JSON for our Blitz Live app's hero card.
    
    JSON Format:
    {{
      "hero_match": {{
        "title": "Exact Match Name (e.g. Bangladesh vs India)",
        "status": "LIVE NOW",
        "stream_url": "m3u8 url from the data",
        "user_agent": "Default",
        "referer": "Default"
      }}
    }}
    
    Warning: NO markdown tags, NO backticks, NO text. Output ONLY the JSON object.
    """
    
    try:
        # ২০২৬ গুগলে সার্চ টুলের আপডেট সিনট্যাক্স
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"AI Generation Error: {str(e)}")
        return ""

if __name__ == "__main__":
    print("🚀 Blitz Live Engine Starting...")
    
    raw_data = fetch_iptv_links()
    ai_raw_output = generate_smart_json(raw_data)
    
    print(f"--- AI RAW OUTPUT ---\n{ai_raw_output}\n---------------------")

    try:
        # জেসন ক্লিন করার প্রো-লজিক (এআই ভুল করলেও ফিক্স করবে)
        clean_json = ai_raw_output
        if "{" in clean_json:
            clean_json = clean_json[clean_json.find("{"):clean_json.rfind("}")+1]
        
        json_obj = json.loads(clean_json)
        
        # স্ট্রাকচার চেক
        if 'hero_match' not in json_obj:
            raise ValueError("Invalid structure")

        # গিটহাবে সেভ করা
        with open("live.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(json_obj, indent=2))
            
        print(f"✅ SUCCESS: {json_obj['hero_match']['title']} is updated!")
        
    except Exception as e:
        print(f"❌ FAILED to update: {str(e)}")
        # ফেইল-সেফ ডাটা (যাতে অ্যাপ না ভাঙ্গে)
        fallback = {
            "hero_match": {
                "title": "Match Schedule Updating...",
                "status": "Check Back in 5 Mins",
                "stream_url": "",
                "user_agent": "Default",
                "referer": "Default"
            }
        }
        with open("live.json", "w") as f:
            f.write(json.dumps(fallback))
