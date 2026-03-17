import os
import json
import requests
from google import genai
from google.genai import types

# ১. জেমিনি ক্লায়েন্ট সেটআপ
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def fetch_iptv_links():
    try:
        response = requests.get("https://iptv-org.github.io/api/streams.json", timeout=15)
        data = response.json()
        target_ids = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in', 'GaziTV.bd', 'Willow.us']
        streams = [s for s in data if s.get('channel') in target_ids]
        return str(streams[:10])
    except:
        return "[]"

def generate_smart_json(iptv_data):
    prompt = f"""
    Search Google for any LIVE major sports matches happening now (March 17, 2026).
    Pick the best match and match with this IPTV data: {iptv_data}
    Output ONLY ONE valid JSON object for Blitz Live app.
    
    Structure:
    {{
      "hero_match": {{
        "title": "Match Name",
        "status": "LIVE NOW",
        "stream_url": "url",
        "user_agent": "Default",
        "referer": "Default"
      }}
    }}
    CRITICAL: Output exactly ONE JSON object. No repetitions.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"AI Error: {str(e)}")
        return ""

if __name__ == "__main__":
    print("🚀 Blitz Live Engine Starting...")
    raw = fetch_iptv_links()
    ai_output = generate_smart_json(raw)
    
    print(f"--- AI RAW OUTPUT ---\n{ai_output}\n---------------------")

    try:
        # জেসন ক্লিন করার "বুলেটপ্রুফ" লজিক
        clean_json = ai_output
        if "{" in clean_json:
            # প্রথম '{' থেকে শুরু করে প্রথম '}' পর্যন্ত অংশটুকু শুধু নিবে
            # এতে রিপিটেড জেসন থাকলে পরের গুলো বাদ পড়ে যাবে
            start_index = clean_json.find("{")
            
            # নিখুঁত ব্র্যাকেট ম্যাচিং লজিক
            count = 0
            end_index = -1
            for i in range(start_index, len(clean_json)):
                if clean_json[i] == '{': count += 1
                elif clean_json[i] == '}': count -= 1
                if count == 0:
                    end_index = i
                    break
            
            clean_json = clean_json[start_index:end_index+1]
        
        json_obj = json.loads(clean_json)
        
        with open("live.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(json_obj, indent=2))
        print(f"✅ SUCCESS: {json_obj['hero_match']['title']} is now LIVE!")
        
    except Exception as e:
        print(f"❌ PARSE ERROR: {str(e)}")
        fallback = {"hero_match": {"title": "Live Match Loading...", "status": "Updating...", "stream_url": "", "user_agent": "Default", "referer": "Default"}}
        with open("live.json", "w") as f:
            f.write(json.dumps(fallback))
