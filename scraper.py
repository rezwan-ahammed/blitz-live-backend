import os
import json
import requests
import logging
import re
from datetime import datetime
from google import genai
from google.genai import types

# ১. লগিং এবং ক্লায়েন্ট সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def fetch_premium_pool():
    """আপনার রিসার্চ করা সোর্সগুলো থেকে লিঙ্ক এবং কুকি এক্সট্রাক্ট করা"""
    logger.info("📡 Hunting for fresh tokens and cookies...")
    pool = []
    
    sources = [
        {"url": "https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/main/Fancode_hls_m3u8.Json", "type": "fancode"},
        {"url": "https://raw.githubusercontent.com/Gtajisan/Toffee-Auto-Update-Playlist/main/toffee_channel_data.json", "type": "toffee"}
    ]
    
    for src in sources:
        try:
            r = requests.get(src["url"], timeout=15)
            if r.status_code == 200:
                data = r.json()
                if src["type"] == "fancode":
                    for m in data.get("matches", []):
                        pool.append({
                            "name": m.get("event_name", "Live Match"),
                            "url": m.get("stream_url", ""),
                            "cookie": m.get("cookie", ""), # ফ্যানকোড টোকেন
                            "ref": "https://www.fancode.com/"
                        })
                elif src["type"] == "toffee":
                    for c in data.get("channels", []):
                        pool.append({
                            "name": c.get("name", "Local TV"),
                            "url": c.get("link", ""),
                            "cookie": c.get("cookie", ""), # টফি বিডিআইএক্স কুকি
                            "ref": "https://toffeelive.com/"
                        })
        except Exception as e:
            logger.warning(f"⚠️ Source failed: {src['url'][:30]}... {str(e)}")
            
    # গ্লোবাল ব্যাকআপ (যদি সব ফেইল করে)
    pool.append({"name": "Red Bull TV", "url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8", "cookie": "", "ref": ""})
    return pool

def clean_and_verify(parsed_json, pool):
    """Firewall: এআই যেন ডাটা নষ্ট না করতে পারে"""
    valid_urls = {s["url"]: s for s in pool}
    default_img = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop"
    
    def process_match(match):
        u = match.get("url") or match.get("stream_url")
        if u in valid_urls:
            # এআই যদি কুকি বা রেফারার মিস করে, পাইথন সেটা পুল থেকে রিস্টোর করবে
            match["stream_url" if "stream_url" in match else "url"] = u
            match["cookie"] = valid_urls[u]["cookie"]
            match["referer"] = valid_urls[u]["ref"]
        else:
            # যদি এআই ভুল লিঙ্ক দেয়, প্রথম ভ্যালিড লিঙ্কটা বসিয়ে দাও
            fallback = pool[0]
            match["stream_url" if "stream_url" in match else "url"] = fallback["url"]
            match["cookie"] = fallback["cookie"]
            match["referer"] = fallback["ref"]
            
        if "image_url" not in match or "example.com" in str(match["image_url"]):
            match["image_url"] = default_img
        return match

    parsed_json["hero_match"] = process_match(parsed_json.get("hero_match", {}))
    if "ranked_matches" in parsed_json:
        parsed_json["ranked_matches"] = [process_match(m) for m in parsed_json["ranked_matches"]]
        
    return parsed_json

def generate_live_data(pool):
    """Gemini AI - শিডিউল এনালাইজার এবং ইমেজ ডিজাইনার"""
    current_time = datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    # এআই-কে শুধু নাম এবং ইউআরএল দিচ্ছি যাতে সে কনফিউজ না হয়
    pool_for_ai = [{"name": s["name"], "url": s["url"]} for s in pool]
    
    prompt = f"""
    Today: {current_time}.
    MISSION: Map today's REAL matches (Search Google) to these streams: {json.dumps(pool_for_ai[:25])}
    
    STRICT RULES:
    1. Only use URLs from the list. 
    2. Pick the best match for 'hero_match'.
    3. Use professional sports images from Unsplash.
    4. MUST keep the JSON structure exactly as below.
    
    OUTPUT:
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW",
        "stream_url": "URL_FROM_LIST",
        "cookie": "",
        "image_url": "IMAGE_URL",
        "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "referer": "Default"
      }},
      "ranked_matches": [
        {{ "title": "Name", "time": "LIVE", "url": "URL_FROM_LIST", "image_url": "IMAGE_URL" }}
      ],
      "summary": "Brief update."
    }}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-flash-lite-latest',
            contents=prompt,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1)
        )
        
        output = response.text.strip()
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            parsed = json.loads(json_match.group())
            return clean_and_verify(parsed, pool)
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
    return None

def main():
    print("🚀 BLITZ LIVE - Cookie-Aware Engine v4.0")
    pool = fetch_premium_pool()
    if not pool: return
    
    final_json = generate_live_data(pool)
    if final_json:
        final_json['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
        print("✅ live.json updated with cookies!")

if __name__ == "__main__":
    main()
