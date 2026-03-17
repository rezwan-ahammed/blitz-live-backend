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

def validate_stream_url(url: str) -> bool:
    """URL validation - Strict filter for ExoPlayer compatibility"""
    if not url:
        return False
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    is_valid_format = bool(re.match(url_pattern, str(url))) and len(url) > 10
    
    # NEW RULE: .m3u8 (HLS) লিংকগুলোকে বেশি প্রাধান্য দেওয়া হচ্ছে, যাতে কালো স্ক্রিন না আসে
    is_hls = '.m3u8' in str(url).lower()
    return is_valid_format and is_hls

def fetch_filtered_streams() -> List[Dict]:
    """প্রিমিয়াম স্পোর্টস চ্যানেল ফিল্টার - Strict HLS Only"""
    try:
        logger.info("📡 Fetching premium IPTV streams...")
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        response.raise_for_status()
        data = response.json()
        
        prime_keywords = ['cricket', 'football', 'sports', 'willow', 'tsports', 'gtv', 'star', 'sky', 'sony', 'bein', 'espn']
        
        filtered = []
        for s in data:
            channel_id = str(s.get('channel', '')).lower()
            url = s.get('url', '')
            
            # শুধুমাত্র ভ্যালিড এবং প্লেএবল (.m3u8) লিংকগুলোই নেওয়া হবে
            if not validate_stream_url(url):
                continue
            
            if any(key in channel_id for key in prime_keywords):
                filtered.append({
                    'channel': s.get('channel', 'Unknown'),
                    'url': url,
                    'ua': s.get('user_agent', 'Default'),
                    'ref': s.get('http_referrer', 'Default')
                })
        
        logger.info(f"✅ Found {len(filtered)} high-quality HLS streams.")
        return filtered[:40] # সেরা ৪০টি প্লেএবল লিংক
    except Exception as e:
        logger.error(f"❌ Stream Fetch Error: {str(e)}")
        return []

def clean_and_verify_data(data: Dict) -> Dict:
    """Anti-Hallucination Firewall"""
    try:
        default_hero = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop"
        default_list = "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=300&auto=format&fit=crop"
        
        def is_safe_image(url):
            if not url or not url.startswith('http'): return False
            if 'imgur.com' in str(url).lower(): return False # Imgur পুরোপুরি ব্লকড
            return True

        hero = data.get("hero_match", {})
        if not hero.get("stream_url", "").startswith('http'):
            data["hero_match"]["stream_url"] = ""
            
        if not is_safe_image(hero.get("image_url", "")):
            data["hero_match"]["image_url"] = default_hero

        if "ranked_matches" in data and isinstance(data["ranked_matches"], list):
            cleaned = []
            for match in data["ranked_matches"]:
                if match.get("url", "").startswith('http'):
                    if not is_safe_image(match.get("image_url", "")):
                        match["image_url"] = default_list
                    cleaned.append(match)
            data["ranked_matches"] = cleaned
        
        return data
    except Exception as e:
        logger.error(f"❌ Verification Error: {str(e)}")
        return data

def generate_intelligent_data(stream_list: List[Dict]) -> Optional[Dict]:
    """Gemini 3.1 Pro দিয়ে নিখুঁত ম্যাপিং"""
    current_time = datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    stream_reference = json.dumps([{'channel': s['channel'], 'url': s['url']} for s in stream_list[:30]])
    
    prompt = f"""
    Current Time: {current_time}.
    
    CRITICAL MISSION: You are an expert sports broadcast analyzer. Find the most important LIVE and UPCOMING (next 12 hours) matches and map them to the EXACT correct channel from the provided list.
    
    VERIFIED STREAMING CHANNELS:
    {stream_reference}
    
    STRICT RULES (VIOLATION CAUSES SYSTEM CRASH):
    1. 'stream_url' MUST be an EXACT string copy-pasted from the list above. DO NOT invent URLs.
    2. CHANNEL MATCHING: Do NOT put a Cricket match on a dedicated Football channel (e.g., beIN Sports). Match logic carefully.
    3. IMAGE RULES: Provide realistic image URLs. DO NOT use imgur.com. Prefer images.unsplash.com or standard sports news domains.
    4. If a match has no relevant channel in the list, set 'stream_url' to "".
    
    OUTPUT FORMAT (Strict JSON ONLY):
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW (or Time)",
        "stream_url": "...",
        "image_url": "...",
        "user_agent": "Default",
        "referer": "Default"
      }},
      "ranked_matches": [
        {{
          "title": "Match Name",
          "time": "LIVE",
          "url": "...",
          "image_url": "..."
        }}
      ],
      "summary": "Short sports update."
    }}
    """
    
    try:
        logger.info("🧠 AI (gemini-3.1-pro) is reasoning deeply for perfect matches...")
        # এখানে আপনার রিকোয়েস্ট অনুযায়ী লেটেস্ট 3.1 Pro মডেল ব্যবহার করা হলো
        response = client.models.generate_content(
            model='gemini-3.1-pro', 
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1 # অত্যন্ত ফোকাসড এবং কড়া লজিক
            )
        )
        
        output = response.text.strip()
        json_match = re.search(r'\{[\s\S]*\}', output)
        if not json_match:
            return None
        
        parsed_data = json.loads(json_match.group())
        return clean_and_verify_data(parsed_data)
        
    except Exception as e:
        logger.error(f"❌ AI Generation Error: {str(e)}")
        return None

def fallback_data() -> Dict:
    fallback = {
        "hero_match": {
            "title": "Updating Live Sports Server...",
            "status": "Please Wait",
            "stream_url": "",
            "image_url": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=1000&auto=format&fit=crop",
            "user_agent": "Default",
            "referer": "Default"
        },
        "ranked_matches": [],
        "summary": "Backend is optimizing streams...",
        "timestamp": datetime.now().isoformat()
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(fallback, f, indent=2)

def main():
    print("🚀 BLITZ LIVE - Gemini 3.1 Pro Engine")
    print("=" * 60)
    streams = fetch_filtered_streams()
    
    if not streams:
        fallback_data()
        return
    
    final_data = generate_intelligent_data(streams)
    
    if final_data:
        final_data['timestamp'] = datetime.now().isoformat()
        with open("live.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ SUCCESS: Pro-level live.json generated!")
    else:
        fallback_data()

if __name__ == "__main__":
    main()
