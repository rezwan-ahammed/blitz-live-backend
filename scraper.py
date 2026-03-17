import os
import json
import requests
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
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

def validate_url(url: str) -> bool:
    """URL validation - ensure it's a proper link"""
    if not url:
        return False
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(url_pattern, str(url))) and len(url) > 10

def fetch_filtered_streams() -> List[Dict]:
    """প্রিমিয়াম স্পোর্টস চ্যানেল ফিল্টার"""
    try:
        logger.info("📡 Fetching premium IPTV streams...")
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        response.raise_for_status()
        data = response.json()
        
        prime_keywords = ['cricket', 'football', 'sports']
        secondary_keywords = ['ten', 'willow', 'tsports', 'gtv', 'star', 'sky', 'sony', 'bein', 'ptv', 'astro', 'espn']
        
        filtered = []
        for s in data:
            channel_id = str(s.get('channel', '')).lower()
            url = s.get('url', '')
            
            if not validate_url(url):
                continue
            
            is_prime = any(key in channel_id for key in prime_keywords)
            is_secondary = any(key in channel_id for key in secondary_keywords)
            
            if is_prime or is_secondary:
                filtered.append({
                    'channel': s.get('channel', 'Unknown'),
                    'url': url,
                    'ua': s.get('user_agent', 'Default'),
                    'ref': s.get('http_referrer', 'Default'),
                    'priority': 1 if is_prime else 2
                })
        
        filtered.sort(key=lambda x: x['priority'])
        logger.info(f"✅ Found {len(filtered)} verified sports streams.")
        return filtered[:40] 
    except Exception as e:
        logger.error(f"❌ Stream Fetch Error: {str(e)}")
        return []

def clean_and_verify_data(data: Dict) -> Dict:
    """সমস্ত ইউআরএল (স্ট্রিম + ইমেজ) পরিষ্কার এবং যাচাই করুন"""
    try:
        # হিরো ম্যাচ চেক
        hero = data.get("hero_match", {})
        if not validate_url(hero.get("stream_url", "")):
            data["hero_match"]["stream_url"] = ""
            
        # ইমেজ ইউআরএল ভ্যালিডেশন (যদি এআই উল্টাপাল্টা কিছু দেয়)
        if not validate_url(hero.get("image_url", "")):
            # ডিফল্ট স্পোর্টস ব্যাকগ্রাউন্ড
            data["hero_match"]["image_url"] = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop"

        # র‍্যাঙ্কড ম্যাচ চেক
        if "ranked_matches" in data and isinstance(data["ranked_matches"], list):
            cleaned_matches = []
            for match in data["ranked_matches"]:
                if validate_url(match.get("url", "")):
                    if not validate_url(match.get("image_url", "")):
                        match["image_url"] = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=300&auto=format&fit=crop"
                    cleaned_matches.append(match)
            data["ranked_matches"] = cleaned_matches
        
        # 🧠 স্মার্ট ফলব্যাক: যদি হিরো ম্যাচ খালি থাকে!
        if not data.get("hero_match", {}).get("title") or not data.get("hero_match", {}).get("stream_url"):
            logger.info("⚡ Hero match stream is empty. Injecting top ranked match!")
            if data.get("ranked_matches") and len(data["ranked_matches"]) > 0:
                top_match = data["ranked_matches"][0]
                data["hero_match"]["title"] = top_match.get("title")
                data["hero_match"]["status"] = top_match.get("time")
                data["hero_match"]["stream_url"] = top_match.get("url")
                data["hero_match"]["image_url"] = top_match.get("image_url")
                
        return data
    except Exception as e:
        logger.error(f"❌ Verification Error: {str(e)}")
        return data

def generate_intelligent_data(stream_list: List[Dict]) -> Optional[Dict]:
    """এআই দিয়ে ডাটা তৈরি (ইমেজ সাপোর্ট সহ)"""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    stream_reference = json.dumps([{'channel': s['channel'], 'url': s['url']} for s in stream_list[:30]])
    
    # প্রম্পটে image_url ফিল্ডটি যুক্ত করা হয়েছে
    prompt = f"""
    Today is {current_date}.
    
    CRITICAL MISSION: Find LIVE and UPCOMING sports matches.
    
    VERIFIED STREAMING CHANNELS:
    {stream_reference}
    
    OUTPUT (Valid JSON ONLY):
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW",
        "stream_url": "exact_url_from_list_or_empty",
        "image_url": "Find a high-quality horizontal image URL of this sport/team from web",
        "user_agent": "Default",
        "referer": "Default"
      }},
      "ranked_matches": [
        {{
          "title": "Match Name",
          "time": "LIVE",
          "url": "exact_url_from_list_or_empty",
          "image_url": "Find a small image URL of this sport/team from web"
        }}
      ],
      "summary": "Brief update."
    }}
    
    RULES:
    1. 'stream_url' MUST be an exact URL from the provided list.
    2. 'image_url' MUST be a valid 'http/https' image link (.jpg/.png/.webp).
    """
    
    try:
        logger.info("🧠 AI (gemini-flash-lite-latest) analyzing with images...")
        response = client.models.generate_content(
            model='gemini-flash-lite-latest', 
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2 
            )
        )
        
        output = response.text.strip()
        json_match = re.search(r'\{[\s\S]*\}', output)
        if not json_match:
            return None
        
        parsed_data = json.loads(json_match.group())
        parsed_data = clean_and_verify_data(parsed_data)
        return parsed_data
        
    except Exception as e:
        logger.error(f"❌ AI Generation Error: {str(e)}")
        return None

def fallback_data() -> Dict:
    fallback = {
        "hero_match": {
            "title": "Sports Update",
            "status": "Connecting...",
            "stream_url": "",
            "image_url": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop",
            "user_agent": "Default",
            "referer": "Default"
        },
        "ranked_matches": [],
        "summary": "Fetching schedules...",
        "timestamp": datetime.now().isoformat()
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(fallback, f, indent=2)

def main():
    print("🚀 BLITZ LIVE - Masterpiece Engine (With Images)")
    streams = fetch_filtered_streams()
    if not streams:
        fallback_data()
        return
    
    final_data = generate_intelligent_data(streams)
    
    if final_data:
        final_data['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: live.json saved with images!")
    else:
        fallback_data()

if __name__ == "__main__":
    main()
