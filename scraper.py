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
    """ইন্টারনেট থেকে কিছু সম্ভাব্য স্পোর্টস চ্যানেলের লিংক জোগাড় করা"""
    try:
        # iptv-org এর ডাটাবেস থেকে স্ট্রীম লিস্ট আনা
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        
        # কিছু পপুলার স্পোর্টস আইডি (টি-স্পোর্টস, স্টার স্পোর্টস, পিটিভি ইত্যাদি)
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us', 'AstroCricket.my']
        streams = [s for s in data if s.get('channel') in target_ids]
        
        return str(streams[:15]) # এআইকে সেরা ১৫টি স্ট্রীম ডাটা পাঠানো
    except Exception as e:
        return f"Fetch Error: {str(e)}"

def generate_smart_json(iptv_data):
    """গুগল সার্চ ব্যবহার করে আজকের খেলা খুঁজে জেসন তৈরি করা"""
    
    # এআই-এর জন্য প্রম্পট: এখানে আমরা তাকে গুগল সার্চ করতে বলছি
    prompt = f"""
    Step 1: Use Google Search to find which major Cricket or Football matches are happening RIGHT NOW (March 17, 2026).
    Step 2: Look at this IPTV stream data: {iptv_data}
    Step 3: Create a 'Hero Card' JSON for 'Blitz Live' app. 
    
    Rules:
    - Title: Must be the specific match name (e.g. 'Bangladesh vs Sri Lanka' or 'Real Madrid vs Chelsea').
    - Status: Use something catchy like 'LIVE | 1st Innings' or 'LIVE | 75th Min'.
    - stream_url: Pick the MOST relevant m3u8 link from the provided IPTV data.
    - If no big match is live, show the next big upcoming match.
    
    Output ONLY pure JSON. NO markdown, NO backticks.
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
        # ২০২৬ স্টাইল: গুগল সার্চ টুল এনাবেল করা
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
            )
        )
        
        output = response.text.strip()
        
        # জেসন ক্লিন করা (যদি এআই ফালতু কথা লিখে থাকে)
        if "{" in output:
            output = output[output.find("{"):output.rfind("}")+1]
        
        return output
    except Exception as e:
        return f"AI Error: {str(e)}"

if __name__ == "__main__":
    print("🚀 Blitz Live Backend Starting...")
    
    print("📡 Fetching IPTV links...")
    iptv_raw = fetch_iptv_links()
    
    print("🧠 AI is searching the internet and matching data...")
    final_json = generate_smart_json(iptv_raw)
    
    try:
        # জেসন ভ্যালিডেশন
        json_obj = json.loads(final_json)
        
        # গিটহাবে সেভ করার জন্য রাইট করা
        with open("live.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(json_obj, indent=2))
            
        print("✅ SUCCESS: live.json updated with real-time match data!")
        print(f"Match Title: {json_obj['hero_match']['title']}")
        
    except Exception as e:
        print(f"❌ FAILED to generate valid JSON: {str(e)}")
        # ফেইল-সেফ ডাটা
        fallback = {
            "hero_match": {
                "title": "Live Sports Update",
                "status": "Check Back Soon",
                "stream_url": "",
                "user_agent": "Default",
                "referer": "Default"
            }
        }
        with open("live.json", "w") as f:
            f.write(json.dumps(fallback))
