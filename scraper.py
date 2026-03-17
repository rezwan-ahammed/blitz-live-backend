import os
import json
import requests
import logging
import re
from datetime import datetime
from google import genai
from google.genai import types

# ১. প্রফেশনাল লগিং এবং ক্লায়েন্ট সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY missing!")
    exit(1)

client = genai.Client(api_key=api_key)

def fetch_github_raw_data():
    """আপনার রিসার্চ করা ডাইনামিক সোর্সগুলো থেকে ডাটা এক্সট্রাক্ট করা"""
    logger.info("📡 Scanning GitHub for dynamic match tokens...")
    stream_pool = []
    
    sources = [
        # FanCode (Cricket/Football)
        {"url": "https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/main/Fancode_hls_m3u8.Json", "type": "fancode"},
        # Toffee (Local Channels)
        {"url": "https://raw.githubusercontent.com/Gtajisan/Toffee-Auto-Update-Playlist/main/toffee_channel_data.json", "type": "toffee"}
    ]
    
    for src in sources:
        try:
            r = requests.get(src["url"], timeout=15)
            if r.status_code == 200:
                data = r.json()
                if src["type"] == "fancode":
                    for m in data.get("matches", []):
                        if m.get("stream_url"):
                            stream_pool.append({"name": m.get("event_name"), "url": m.get("stream_url")})
                elif src["type"] == "toffee":
                    for c in data.get("channels", []):
                        if c.get("link"):
                            stream_pool.append({"name": c.get("name"), "url": c.get("link")})
        except Exception as e:
            logger.warning(f"⚠️ Source failed: {src['url'][:30]}... {str(e)}")
            
    # ব্যাকআপ গ্লোবাল চ্যানেল (যদি উপরের সোর্সগুলো খালি থাকে)
    stream_pool.append({"name": "Red Bull TV Live", "url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8"})
    stream_pool.append({"name": "Al Jazeera Live English", "url": "https://live-hls-web-aje.getaj.net/AJE/index.m3u8"})
    
    logger.info(f"🎯 Total {len(stream_pool)} verified streams in pool.")
    return stream_pool

def clean_and_verify(parsed_json, pool):
    """Firewall: ভুয়া ছবি এবং ভুল লিঙ্ক ঠিক করা"""
    valid_urls = [s["url"] for s in pool]
    default_img = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop"
    
    def is_safe(url):
        u = str(url).lower()
        return u.startswith('http') and 'example.com' not in u and 'imgur.com' not in u

    # হিরো ম্যাচ চেক
    hero = parsed_json.get("hero_match", {})
    if hero.get("stream_url") not in valid_urls:
        parsed_json["hero_match"]["stream_url"] = valid_urls[0] if valid_urls else ""
    if not is_safe(hero.get("image_url")):
        parsed_json["hero_match"]["image_url"] = default_img

    # র‍্যাঙ্কড ম্যাচেস চেক
    if "ranked_matches" in parsed_json:
        for m in parsed_json["ranked_matches"]:
            if m.get("url") not in valid_urls:
                m["url"] = valid_urls[0] if valid_urls else ""
            if not is_safe(m.get("image_url")):
                m["image_url"] = default_img
                
    return parsed_json

def generate_live_json(pool):
    """এআই দিয়ে রিয়েল-টাইম শিডিউল এবং ইমেজ ম্যাপিং করা"""
    current_time = datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    pool_str = json.dumps(pool[:30], indent=2) # এআই-কে সেরা ৩০টি অপশন দেওয়া হচ্ছে
    
    prompt = f"""
    Current Time: {current_time}.
    
    MISSION: 
    1. Search Google for today's LIVE cricket and football matches.
    2. Map them only to the URLs from this pool: {pool_str}
    
    STRICT RULES:
    - stream_url MUST be from the pool.
    - Match Bangladesh/IPL/BPL matches with FanCode or Toffee URLs.
    - Provide high-quality sports images (Unsplash/Official sites). No example.com.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW",
        "stream_url": "URL_FROM_POOL",
        "image_url": "REAL_IMAGE_URL",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "Default"
      }},
      "ranked_matches": [
        {{
          "title": "Match Name",
          "time": "LIVE",
          "url": "URL_FROM_POOL",
          "image_url": "REAL_IMAGE_URL"
        }}
      ],
      "summary": "Brief update."
    }}
    """
    
    try:
        logger.info("🧠 AI is analyzing today's matches and mapping URLs...")
        response = client.models.generate_content(
            model='gemini-flash-lite-latest', # লেটেস্ট এবং ফাস্ট
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1
            )
        )
        
        output = response.text.strip()
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            parsed = json.loads(json_match.group())
            return clean_and_verify(parsed, pool)
        return None
    except Exception as e:
        logger.error(f"❌ AI Error: {str(e)}")
        return None

def main():
    print("🚀 BLITZ LIVE - The Research-Based Engine v3.0")
    print("=" * 60)
    
    # ১. আপনার গিটহাব সোর্স থেকে ডাটা আনা
    pool = fetch_github_raw_data()
    
    if not pool:
        logger.error("❌ Pool is empty. Check GitHub sources.")
        return
        
    # ২. এআই দিয়ে আজকের ম্যাচের সাথে লিঙ্ক ম্যাপ করা
    final_data = generate_live_json(pool)
    
    if final_data:
        final_data['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: live.json updated perfectly!")
    else:
        logger.error("❌ AI failed to format data.")

if __name__ == "__main__":
    main()
