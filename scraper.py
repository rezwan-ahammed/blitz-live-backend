import os
import json
import requests
import logging
from datetime import datetime
from google import genai
from google.genai import types

# ১. প্রফেশনাল লগিং সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ২. জেমিনি ক্লায়েন্ট সেটআপ
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY is missing! Check GitHub Secrets.")
    exit(1)

client = genai.Client(api_key=api_key)

def fetch_filtered_streams():
    """আপনার অ্যাপের জন্য সেরা স্পোর্টস চ্যানেলগুলো ফিল্টার করা"""
    try:
        logger.info("📡 Fetching raw IPTV streams...")
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        
        # স্পোর্টস কি-ওয়ার্ডস
        keywords = ['sports', 'cricket', 'football', 'ten', 'willow', 'tsports', 'gtv', 'star', 'sky', 'sony', 'bein', 'ptv', 'astro']
        
        filtered = []
        for s in data:
            channel_id = str(s.get('channel', '')).lower()
            if any(key in channel_id for key in keywords):
                filtered.append({
                    'channel': s.get('channel'),
                    'url': s.get('url'),
                    'ua': s.get('user_agent', 'Default'),
                    'ref': s.get('http_referrer', 'Default')
                })
        
        logger.info(f"✅ Found {len(filtered)} potential sports streams.")
        return filtered[:50] # এআইকে সেরা ৫০টি অপশন দিচ্ছি যাতে সে ফোকাসড থাকে
    except Exception as e:
        logger.error(f"❌ Fetch Error: {str(e)}")
        return []

def generate_intelligent_data(stream_list):
    """AI দিয়ে লাইভ ম্যাচ খুঁজে বের করা এবং পারফেক্ট লিংক ম্যাচ করা"""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    prompt = f"""
    Today is {current_date}. 
    
    TASK:
    1. Search Google for today's LIVE major cricket and football matches.
    2. From the IPTV list below, find the EXACT working channels broadcasting these matches.
    
    IPTV LIST:
    {json.dumps(stream_list)}
    
    CRITICAL RULES FOR 'stream_url' (MUST OBEY):
    - It MUST ONLY be a valid URL starting with 'http' or 'https'.
    - NEVER write sentences, explanations, or text in the 'stream_url' field.
    - If NO valid URL is found for a match, set 'stream_url' to "" (empty string).
    - The 'hero_match' MUST be a match that has a valid, working URL from the list.
    
    OUTPUT STRUCTURE (Strict JSON ONLY):
    {{
      "hero_match": {{
        "title": "Exact Match Name (e.g., Bangladesh vs India)",
        "status": "LIVE NOW (or score)",
        "stream_url": "http://...",
        "user_agent": "Default",
        "referer": "Default"
      }},
      "ranked_matches": [
         {{ 
            "title": "Match Name", 
            "time": "LIVE", 
            "url": "http://..." 
         }}
      ],
      "summary": "Brief sports update summary."
    }}
    """
    
    try:
        logger.info("🧠 AI (gemini-flash-lite-latest) is analyzing matches...")
        response = client.models.generate_content(
            model='gemini-flash-lite-latest', # আপনার রিকুয়েস্ট করা লেটেস্ট মডেল
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2 # কম টেম্পারেচার = ফোকাসড এবং নির্ভুল ডাটা
            )
        )
        
        output = response.text.strip()
        logger.info("Raw AI response generated.")
        
        # JSON ক্লিন-আপ
        if "{" in output:
            output = output[output.find("{"):output.rfind("}")+1]
        
        return json.loads(output)
    except Exception as e:
        logger.error(f"❌ AI Logic Error: {str(e)}")
        return None

def fallback_data():
    """ফেইল-সেফ ডাটা যাতে অ্যাপ ক্র্যাশ না করে"""
    fallback = {
        "hero_match": {
            "title": "Sports Update",
            "status": "Check Back Later",
            "stream_url": "",
            "user_agent": "Default",
            "referer": "Default"
        },
        "ranked_matches": [],
        "summary": "Updating match schedules...",
        "timestamp": datetime.now().isoformat()
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(fallback, f, indent=2)

def main():
    print("🚀 Blitz Live Engine Starting (Flash Lite)...")
    streams = fetch_filtered_streams()
    
    if not streams:
        logger.warning("⚠️ No streams fetched, using fallback.")
        fallback_data()
        return

    final_data = generate_intelligent_data(streams)
    
    if final_data:
        # 🛡️ আল্টিমেট সেফটি চেক: হিরো ম্যাচের ইউআরএল ঠিক আছে তো?
        hero_url = final_data.get("hero_match", {}).get("stream_url", "")
        if not hero_url.startswith("http"):
            logger.warning(f"⚠️ AI hallucinates text in stream_url: '{hero_url}'. Fixing to empty string.")
            final_data["hero_match"]["stream_url"] = ""

        # র‍্যাঙ্কড ম্যাচের ইউআরএল চেক
        if "ranked_matches" in final_data:
            for match in final_data["ranked_matches"]:
                if not match.get("url", "").startswith("http"):
                    match["url"] = ""

        final_data['timestamp'] = datetime.now().isoformat()
        
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: live.json updated perfectly!")
    else:
        logger.warning("⚠️ Using fallback data due to AI parsing failure.")
        fallback_data()

if __name__ == "__main__":
    main()
