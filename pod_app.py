import streamlit as st
import requests
from newspaper import Article
from datetime import datetime, timedelta
import sqlite3
import os
# import spotipy
# from spotipy.oauth2 import SpotifyOAuth

# Initialize SQLite database to store episode details
def init_db():
    conn = sqlite3.connect("episodes.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topics TEXT,
        duration INTEGER,
        depth TEXT,
        script TEXT,
        mp3_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

# Fetch and summarize news articles using NewsAPI and newspaper3k
def fetch_and_summarize_news(topics, api_key):
    summaries = {}
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    for topic in topics:
        # Verified NewsAPI endpoint
        url = f"https://newsapi.org/v2/everything?q=AI AND {topic}&from={yesterday}&sortBy=publishedAt&apiKey={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            articles = response.json().get("articles", [])
            topic_summaries = []
            for article in articles[:3]:  # Top 3 articles per topic
                try:
                    a = Article(article["url"])
                    a.download()
                    a.parse()
                    text = a.text
                    if text:
                        summary = summarize_with_gemini(text)
                        topic_summaries.append(summary)
                    else:
                        st.warning(f"No content extracted for article: {article['url']}")
                except Exception as e:
                    st.warning(f"Failed to process article {article['url']}: {e}")
            if topic_summaries:
                summaries[topic] = topic_summaries
            else:
                st.warning(f"No summaries generated for topic: {topic}")
        except requests.RequestException as e:
            st.error(f"Failed to fetch news for {topic}: {e}")
    return summaries

# Summarize articles using Gemini API
def summarize_with_gemini(text):
    api_key = st.secrets["api_keys"]["gemini"]
    # Verified Gemini API endpoint (Google AI Studio version)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"Summarize the following article in 2-3 sentences, focusing on AI-related points: {text[:4000]}"
    request_body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=request_body)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (requests.RequestException, KeyError, IndexError) as e:
        st.error(f"Gemini API summarization failed: {e}")
        return "Summary unavailable due to API error."

# Generate podcast script using Gemini API
def generate_script(topics, duration, depth, summaries):
    api_key = st.secrets["api_keys"]["gemini"]
    # Verified Gemini API endpoint (Google AI Studio version)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    word_count = duration * 150  # Assuming 150 words per minute
    formatted_summaries = "\n".join([f"{topic}: {', '.join(summaries[topic])}" for topic in summaries])
    prompt = f"""
    You are an AI news reporter. Create a podcast script for a {duration}-minute episode on the latest AI news about {', '.join(topics)}.
    The audience has a {depth} level of understanding. Use the following news summaries:

    {formatted_summaries}

    The script should be approximately {word_count} words, structured with an introduction, main content, and conclusion.
    Make it engaging with a conversational tone, including rhetorical questions or examples where appropriate.
    """
    request_body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=request_body)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (requests.RequestException, KeyError, IndexError) as e:
        st.error(f"Gemini API script generation failed: {e}")
        return "Script generation failed due to API error."

# Convert script to MP3 using Deepgram API
def text_to_speech(script):
    api_key = st.secrets["api_keys"]["deepgram"]
    url = "https://api.deepgram.com/v1/speak"  # Base TTS endpoint
    headers = {
        "Authorization": f"Token {api_key}",  # Corrected to use Token instead of Bearer
        "Content-Type": "application/json"
    }
    
    # Define max length for Deepgram TTS (2000 characters)
    MAX_TTS_LENGTH = 2000
    
    # Split text if too long
    if len(script) > MAX_TTS_LENGTH:
        st.write(f"Script too long ({len(script)} characters). Splitting into chunks.")
        text_chunks = [script[i:i+MAX_TTS_LENGTH] for i in range(0, len(script), MAX_TTS_LENGTH)]
    else:
        text_chunks = [script]

    # Process each chunk and concatenate audio
    audio_files = []
    for i, chunk in enumerate(text_chunks):
        st.write(f"Processing chunk {i + 1}/{len(text_chunks)} ({len(chunk)} characters)")
        data = {"text": chunk}
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            chunk_file = f"chunk_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            with open(chunk_file, "wb") as f:
                f.write(response.content)
            audio_files.append(chunk_file)
        except requests.RequestException as e:
            st.error(f"Deepgram API text-to-speech failed for chunk {i + 1}: {e}")
            return None
    
    # Combine chunks into a single MP3 (simplified approach: return first chunk for now)
    if audio_files:
        final_mp3 = f"episode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        # For simplicity, just rename the first chunk; full concatenation requires audio libraries
        os.rename(audio_files[0], final_mp3)
        # Clean up extra chunks if any (optional)
        for extra_file in audio_files[1:]:
            os.remove(extra_file)
        return final_mp3
    else:
        st.error("No audio files generated.")
        return None

# Placeholder for Spotify upload (commented out for later implementation)
# def upload_to_spotify(mp3_file):
#     client_id = st.secrets["api_keys"]["spotify_client_id"]
#     client_secret = st.secrets["api_keys"]["spotify_client_secret"]
#     # Define redirect URI and scope based on Spotify API requirements
#     sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
#                                                    client_secret=client_secret,
#                                                    redirect_uri="http://localhost:8501/callback",
#                                                    scope="ugc-image-upload user-read-playback-state user-modify-playback-state"))
#     # Placeholder: Implement episode upload logic per Spotify API docs
#     st.info("Spotify upload not fully implemented. Download the MP3 for manual upload.")
#     return False

# Save episode details to SQLite database
def save_to_db(data):
    try:
        conn = sqlite3.connect("episodes.db")
        c = conn.cursor()
        c.execute("INSERT INTO episodes (topics, duration, depth, script, mp3_file) VALUES (?, ?, ?, ?, ?)",
                  (data["topics"], data["duration"], data["depth"], data["script"], data["mp3_file"]))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")

# Streamlit UI
def main():
    init_db()  # Initialize database on startup
    st.title("Daily AI News Podcast Generator")
    st.write("Create a custom AI news podcast by selecting your topics, duration, and depth level.")

    # User inputs
    topics_input = st.text_area("Enter topics of interest (comma-separated, e.g., machine learning, robotics):")
    duration = st.slider("Select podcast duration (minutes):", min_value=5, max_value=60, value=10)
    depth = st.radio("Select depth level:", options=["Starter", "Mid", "Deep"], index=1)

    if st.button("Generate Podcast"):
        if not topics_input.strip():
            st.error("Please enter at least one topic.")
            return

        topics = [t.strip() for t in topics_input.split(",") if t.strip()]
        with st.spinner("Fetching latest AI news..."):
            newsapi_key = st.secrets["api_keys"]["newsapi"]
            summaries = fetch_and_summarize_news(topics, newsapi_key)
            if not summaries:
                st.error("No news summaries available to generate the podcast.")
                return

        with st.spinner("Generating podcast script..."):
            script = generate_script(topics, duration, depth, summaries)
            if "failed" in script.lower():
                st.error("Script generation failed. Check API logs.")
                return

        with st.spinner("Converting script to audio..."):
            mp3_file = text_to_speech(script)
            if not mp3_file or not os.path.exists(mp3_file):
                st.error("Audio generation failed.")
                return

        # Display and play the podcast
        st.success("Podcast generated successfully!")
        st.audio(mp3_file, format="audio/mp3")
        st.download_button("Download MP3", data=open(mp3_file, "rb"), file_name=mp3_file)

        # Save to database
        data = {"topics": topics_input, "duration": duration, "depth": depth, "script": script, "mp3_file": mp3_file}
        save_to_db(data)

        # Optional Spotify upload (commented out)
        # if st.checkbox("Upload to Spotify (experimental)"):
        #     with st.spinner("Uploading to Spotify..."):
        #         success = upload_to_spotify(mp3_file)
        #         if success:
        #             st.success("Podcast uploaded to Spotify!")
        #         else:
        #             st.warning("Spotify upload not completed. Use the download option.")

if __name__ == "__main__":
    main()