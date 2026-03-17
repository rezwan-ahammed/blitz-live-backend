import os
import json
import requests
import logging
from datetime import datetime
from google import genai
from google.genai import types

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def get_premium_persistent_channels():
    """সবসময় কাজ করে এমন কিছু প্রিমিয়াম স্পোর্টস চ্যানেলের ব্যাকআপ (Fallback)"""
    return [
        {"name": "T-Sports HD (BD Matches)", "url": "https://tvsen7.aynaott.com/tsportshd/index.m3u8"},
        {"name": "GTV HD (Cricket)", "url": "https://d2q8p4pe5spbak.cloudfront.net/bpk-tv/GTV_HD/default/index.m3u8"},
        {"name": "Willow TV (Live Cricket)", "url": "https://willow-app.boondocktv.com/willow-hd-1/index.m3u8"},
        {"name": "PTV Sports (Pak/Int. Matches)", "url": "http://103.226.248.53:8080/ptvsports/index.m3u8"},
        {"name": "beIN Sports (Football/UCL)", "url": "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/bein-sports-xtra/playlist.m3u8"},
        {"name": "Sky Sports (Premier League)", "url": "https://skysports.m3u8"} # ডামি বা আপনার হিডেন লিংক
    ]

def fetch_dynamic_live_events():
    """বিভিন্ন রিয়েল-টাইম সোর্স থেকে আজকের ইভেন্ট ডাটা টানা"""
    logger.info("📡 Scanning multiple sources for dynamic live events...")
    live_links = []
    
    # সোর্স ১: গিটহাবের পাবলিক স্পোর্টস ইভেন্ট এপিআই (উদাঃ FanCode বা স্পোর্টস রিপো)
    # [এখানে আপনি টেলিগ্রাম বা গিটহাবের রিয়েল-টাইম .m3u সোর্স বসাতে পারেন]
    try:
        # উদাহরণস্বরূপ একটি কমন ওপেন সোর্স সোর্স
        res = requests.get("https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/main/live.json", timeout=10)
        if res.status_code == 200:
            data = res.json()
            for match in data.get("matches", []):
                if match.get("stream_url"):
                    live_links.append({
                        "name": match.get("title", "Live Match"),
                        "url": match.get("stream_url")
                    })
    except Exception as e:
        logger.warning(f"⚠️ Source 1 failed: {str(e)}")
        
    return live_links

def get_hybrid_stream_pool():
    """সব সোর্স মিলিয়ে একটি মাস্টার পোল তৈরি করা"""
    pool = fetch_dynamic_live_events()
    # যদি ডায়নামিক লিংক না পাওয়া যায় বা কম পাওয়া যায়, তবে ব্যাকআপ চ্যানেলগুলো যোগ করে দেবো
    pool.extend(get_premium_persistent_channels())
    logger.info(f"🎯 Hybrid Pool Ready with {len(pool)} ultra-reliable streams.")
    return pool

def ai_brain_matcher(stream_pool):
    """এআই গুগল সার্চ করে রিয়েল ম্যাচের সাথে স্ট্রিম পোল ম্যাচ করাবে"""
    current_time = datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    pool_data = json.dumps(stream_pool, indent=2)
    
    prompt = f"""
    Time: {current_time}.
    
    MISSION: 
    1. Search Google for today's most popular LIVE and UPCOMING sports matches (Cricket & Football).
    2. Map them ONLY to the working URLs from this HYBRID POOL:
    {pool_data}
    
    STRICT RULES:
    - YOU MUST NOT INVENT URLs. Use EXACT URLs from the HYBRID POOL.
    - Match intelligently: Put Bangladesh matches on T-Sports or GTV. Put international cricket on Willow. Put football on beIN.
    - Provide realistic 'image_url' for each match.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
      "hero_match": {{
        "title": "Clean Match Name",
        "status": "LIVE NOW (or Time)",
        "stream_url": "URL_FROM_POOL",
        "image_url": "REALISTIC_IMAGE_LINK",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "referer": "Default"
      }},
      "ranked_matches": [
        {{
          "title": "Clean Match Name",
          "time": "LIVE",
          "url": "URL_FROM_POOL",
          "image_url": "REALISTIC_IMAGE_LINK"
        }}
      ],
      "summary": "Brief update."
    }}
    """
    
    try:
        logger.info("🧠 AI (gemini-2.0-flash) is mapping real matches to Hybrid Pool...")
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1 # লজিক্যাল ম্যাপিংয়ের জন্য কম টেম্পারেচার
            )
        )
        
        output = response.text.strip()
        start = output.find("{")
        end = output.rfind("}") + 1
        
        if start != -1 and end != 0:
            parsed_json = json.loads(output[start:end])
            
            # 🛡️ ভ্যালিডেশন: হিরো ইউআরএল ঠিক আছে তো?
            hero_url = parsed_json.get("hero_match", {}).get("stream_url", "")
            valid_urls = [s["url"] for s in stream_pool]
            
            if hero_url not in valid_urls and hero_url != "":
                logger.warning("⚠️ AI hallucinated a URL. Reverting to top premium channel.")
                parsed_json["hero_match"]["stream_url"] = valid_urls[0] if valid_urls else ""
                
            return parsed_json
            
        return None
    except Exception as e:
        logger.error(f"❌ AI Mapping Error: {str(e)}")
        return None

def fallback_data() -> dict:
    fallback = {
        "hero_match": {
            "title": "Blitz Sports Hub",
            "status": "Live Channels",
            "stream_url": "https://tvsen7.aynaott.com/tsportshd/index.m3u8",
            "image_url": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop",
            "user_agent": "Default",
            "referer": "Default"
        },
        "ranked_matches": [],
        "summary": "Enjoy premium 24/7 sports channels.",
        "timestamp": datetime.now().isoformat()
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(fallback, f, indent=2)

def main():
    print("🚀 BLITZ LIVE - Hybrid Aggregator Architecture")
    print("=" * 60)
    
    stream_pool = get_hybrid_stream_pool()
    
    if not stream_pool:
        fallback_data()
        return
        
    final_data = ai_brain_matcher(stream_pool)
    
    if final_data:
        final_data['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: Hybrid Data Saved!")
    else:
        logger.warning("⚠️ AI failed to format. Using fallback.")
        fallback_data()

if __name__ == "__main__":
    main()
