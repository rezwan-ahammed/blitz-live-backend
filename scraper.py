import os
import json
import requests
from google import genai
from google.genai import types
from datetime import datetime
import logging

# ১. প্রফেশনাল লগিং সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ২. ক্লায়েন্ট সেটআপ
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def fetch_filtered_streams():
    """আপনার আইডিয়া অনুযায়ী স্পোর্টস চ্যানেলগুলো ফিল্টার করা"""
    try:
        logger.info("📡 Fetching IPTV streams...")
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        
        keywords = ['sports', 'cricket', 'football', 'ten', 'willow', 'tsports', 'gtv', 'star', 'sky', 'sony', 'bein']
        
        filtered = []
        for s in data:
            channel_id = str(s.get('channel', '')).lower()
            if any(key in channel_id for key in keywords):
                filtered.append({
                    'id': s.get('channel'),
                    'url': s.get('url'),
                    'ua': s.get('user_agent', 'Default'),
                    'ref': s.get('http_referrer', 'Default')
                })
        
        logger.info(f"✅ Found {len(filtered)} sports streams")
        return filtered[:60] # এআইকে ৬০টি অপশন দেবো বেছে নেওয়ার জন্য
    except Exception as e:
        logger.error(f"❌ Fetch Error: {str(e)}")
        return []

def generate_intelligent_data(stream_list):
    """গুগল সার্চ ব্যবহার করে ম্যাচ এবং লিংকের মধ্যে পারফেক্ট রিলেশন তৈরি করা"""
    
    current_date = datetime.now().strftime("%B %d, %2026")
    
    prompt = f"""
    Today is {current_date}. 
    
    TASK:
    1. Search Google for today's LIVE major cricket and football matches.
    2. From this IPTV list, find the EXACT channel that broadcasts each match:
    {json.dumps(stream_list)}
    
    MAPPING LOGIC:
    - NZ vs SA -> Look for SuperSport, Sky Sports, or GTV/TSports.
    - Bangladesh Matches -> Priority GTV or T Sports.
    - IPL/India -> Star Sports or Sony Ten.
    - European Football -> beIN Sports or Sony Ten/Sky.
    
    OUTPUT STRUCTURE (Strict JSON):
    {{
      "hero_match": {{
        "title": "Top Popular Live Match Name",
        "status": "LIVE NOW",
        "stream_url": "best working link",
        "user_agent": "ua",
        "referer": "ref"
      }},
      "ranked_matches": [
         {{ "title": "Match Name", "time": "LIVE", "url": "link" }}
      ],
      "summary": "Sports update summary"
    }}
    """
    
    try:
        logger.info("🧠 AI is analyzing and matching streams...")
        response = client.models.generate_content(
            model='gemini-flash-lite-latest',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2 # কম টেম্পারেচার মানে বেশি নির্ভুল ডাটা
            )
        )
        
        output = response.text.strip()
        if "{" in output:
            output = output[output.find("{"):output.rfind("}")+1]
        
        return json.loads(output)
    except Exception as e:
        logger.error(f"❌ AI Logic Error: {str(e)}")
        return None

def main():
    streams = fetch_filtered_streams()
    if not streams:
        return

    final_data = generate_intelligent_data(streams)
    
    if final_data:
        final_data['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: live.json updated with relevant match data!")
    else:
        logger.warning("⚠️ Using fallback data due to AI failure")

if __name__ == "__main__":
    main()
