import os
import json
import requests
import google.generativeai as genai

# ১. Gemini AI সেটআপ করা (আপনার সিক্রেট API Key ব্যবহার করে)
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-pro')

# ২. ইন্টারনেট থেকে কাঁচা (Raw) স্পোর্টস ডেটা সংগ্রহ করা (iptv-org থেকে)
def fetch_raw_sports_data():
    try:
        response = requests.get("https://iptv-org.github.io/api/streams.json")
        data = response.json()
        
        # শুধুমাত্র স্পোর্টস চ্যানেলগুলো ফিল্টার করছি (যাতে AI-এর বুঝতে সুবিধা হয়)
        # এখানে আপনি আপনার পছন্দের চ্যানেলের ID দিতে পারেন
        target_channels = ['TSports.bd', 'StarSports1.in', 'PTVSports.pk', 'SonyTen1.in']
        sports_streams = [stream for stream in data if stream.get('channel') in target_channels]
        
        return str(sports_streams[:10]) # সেরা ১০টি লিংক AI-কে পাঠাবো
    except Exception as e:
        return "Error fetching data"

# ৩. AI-কে দিয়ে কাঁচা ডেটা থেকে সুন্দর JSON তৈরি করানো
def generate_blitz_json(raw_data):
    prompt = f"""
    You are the backend API manager for a sports live streaming app named 'Blitz Live'.
    Here is some raw IPTV stream data fetched right now:
    {raw_data}

    Your task:
    1. Find ONE working sports stream from the data (preferably T Sports or Star Sports).
    2. Format the data into a strict JSON structure for the app's Hero Card.
    3. Make up a realistic current match title based on the channel (e.g., if it's T Sports, write "Bangladesh Match - LIVE", if Star Sports, "India Match - LIVE").
    
    CRITICAL: Output ONLY valid JSON. Do not include markdown tags like ```json or any other text.
    
    Structure must be EXACTLY this:
    {{
      "hero_match": {{
        "title": "<Your Generated Match Title>",
        "status": "LIVE NOW",
        "stream_url": "<The m3u8 url you found>",
        "user_agent": "Default",
        "referer": "Default"
      }}
    }}
    """
    
    response = model.generate_content(prompt)
    output = response.text.strip()
    
    # যদি AI ভুল করে ```json ট্যাগ লাগিয়ে দেয়, সেটা রিমুভ করা
    if output.startswith("```json"):
        output = output[7:-3].strip()
        
    return output

if __name__ == "__main__":
    print("Fetching raw data...")
    raw_data = fetch_raw_sports_data()
    
    print("AI is processing the data...")
    final_json = generate_blitz_json(raw_data)
    
    # 8. live.json ফাইলে ডেটা সেভ করা
    with open("live.json", "w", encoding="utf-8") as f:
        f.write(final_json)
        
    print("Successfully created live.json!")
    print(final_json)
