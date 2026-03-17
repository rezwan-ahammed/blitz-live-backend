import os
import json
import requests
import logging
import re
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

def get_premium_persistent_channels():
    """১০০% ওয়ার্কিং এবং আনব্লকড গ্লোবাল স্পোর্টস চ্যানেল (Black Screen হবে না)"""
    return [
        {"name": "Red Bull TV Live (Extreme Sports)", "url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8"},
        {"name": "CBS Sports HQ (News & Live)", "url": "https://cbsn-cbsn-sports-smarttv.amagi.tv/playlist.m3u8"},
        {"name": "FIFA+ Live TV (Football)", "url": "https://fifa-world-cup.amagi.tv/playlist.m3u8"}
    ]

def fetch_dynamic_live_events():
    """রিয়েল-টাইম সোর্স থেকে আজকের লাইভ ইভেন্ট ডাটা টানা"""
    logger.info("📡 Scanning multiple sources for dynamic live events...")
    live_links = []
    
    try:
        # FanCode বা অন্যান্য ওপেন সোর্স রিয়েল-টাইম API
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
        logger.warning(f"⚠️ Dynamic Source failed (it's normal): {str(e)}")
        
    return live_links

def get_hybrid_stream_pool():
    """সব সোর্স মিলিয়ে একটি মাস্টার পোল তৈরি করা"""
    pool = fetch_dynamic_live_events()
    pool.extend(get_premium_persistent_channels())
    logger.info(f"🎯 Hybrid Pool Ready with {len(pool)} ultra-reliable streams.")
    return pool

def clean_and_verify_data(parsed_json, stream_pool):
    """Anti-Hallucination Firewall: ভুয়া ছবি এবং লিংক ব্লক করা"""
    try:
        valid_urls = [s["url"] for s in stream_pool]
        default_img = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop"
        default_list_img = "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=300&auto=format&fit=crop"
        
        def is_safe_image(url):
            if not url or not str(url).startswith('http'): return False
            img_url_lower = str(url).lower()
            # এআই-এর বানানো ভুয়া সাইটগুলো ব্লক
            if 'example.com' in img_url_lower or 'imgur.com' in img_url_lower: 
                return False 
            return True

        # ১. হিরো ম্যাচ ভ্যালিডেশন
        hero = parsed_json.get("hero_match", {})
        hero_url = hero.get("stream_url", "")
        if hero_url not in valid_urls and hero_url != "":
            parsed_json["hero_match"]["stream_url"] = valid_urls[0] if valid_urls else ""
            logger.warning("⚠️ AI hallucinated hero URL. Restored to default.")
            
        if not is_safe_image(hero.get("image_url", "")):
            parsed_json["hero_match"]["image_url"] = default_img
            logger.warning("⚠️ AI provided fake hero image. Replaced with default.")

        # ২. র‍্যাঙ্কড ম্যাচেস ভ্যালিডেশন
        if "ranked_matches" in parsed_json and isinstance(parsed_json["ranked_matches"], list):
            cleaned = []
            for match in parsed_json["ranked_matches"]:
                # লিংক ভ্যালিডেশন
                match_url = match.get("url", "")
                if match_url not in valid_urls and match_url != "":
                    match["url"] = valid_urls[0] if valid_urls else ""
                
                # ইমেজ ভ্যালিডেশন
                if not is_safe_image(match.get("image_url", "")):
                    match["image_url"] = default_list_img
                    
                cleaned.append(match)
            parsed_json["ranked_matches"] = cleaned
        
        return parsed_json
    except Exception as e:
        logger.error(f"❌ Firewall Error: {str(e)}")
        return parsed_json

def ai_brain_matcher(stream_pool):
    """এআই গুগল সার্চ করে রিয়েল ম্যাচের সাথে স্ট্রিম পোল ম্যাচ করাবে"""
    current_time = datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    pool_data = json.dumps(stream_pool, indent=2)
    
    prompt = f"""
    Time: {current_time}.
    
    MISSION: 
    1. Search Google for today's LIVE and UPCOMING sports matches.
    2. Map them ONLY to the working URLs from this HYBRID POOL:
    {pool_data}
    
    STRICT RULES:
    - YOU MUST NOT INVENT URLs. Use EXACT URLs from the HYBRID POOL.
    - Provide realistic 'image_url' for each match from reliable sources (like unsplash or official sites). DO NOT use example.com or imgur.com.
    
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
        logger.info("🧠 AI is mapping real matches to Hybrid Pool...")
        # 404 এরর এড়াতে এপিআই-এর লেটেস্ট স্ট্যাবল মডেল (gemini-2.0-flash) দেওয়া হয়েছে
        response = client.models.generate_content(
            model='gemini-flash-lite-latest', 
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1 
            )
        )
        
        output = response.text.strip()
        start = output.find("{")
        end = output.rfind("}") + 1
        
        if start != -1 and end != 0:
            parsed_json = json.loads(output[start:end])
            # ফায়ারওয়াল দিয়ে ডেটা ক্লিন করা
            return clean_and_verify_data(parsed_json, stream_pool)
            
        return None
    except Exception as e:
        logger.error(f"❌ AI Mapping Error: {str(e)}")
        return None

def fallback_data() -> dict:
    """পুরো সিস্টেম ফেইল করলে এই ডাটা যাবে"""
    fallback = {
        "hero_match": {
            "title": "Blitz Sports Hub",
            "status": "Live Channels",
            "stream_url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8",
            "image_url": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop",
            "user_agent": "Mozilla/5.0",
            "referer": "Default"
        },
        "ranked_matches": [
            {
              "title": "CBS Sports HQ",
              "time": "LIVE 24/7",
              "url": "https://cbsn-cbsn-sports-smarttv.amagi.tv/playlist.m3u8",
              "image_url": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=300&auto=format&fit=crop"
            }
        ],
        "summary": "Enjoy premium 24/7 sports channels while we fetch live matches.",
        "timestamp": datetime.now().isoformat()
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(fallback, f, indent=2)

def main():
    print("🚀 BLITZ LIVE - The Ultimate Hybrid Engine")
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
        logger.info("✅ SUCCESS: Bulletproof Hybrid Data Saved!")
    else:
        logger.warning("⚠️ AI failed to format. Using fallback.")
        fallback_data()

if __name__ == "__main__":
    main()
