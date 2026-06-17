import os
import requests
from dotenv import load_dotenv

load_dotenv()

class YouTubeStats:
    def __init__(self, channel_id=None):
        self.channel_id = channel_id or os.getenv("YOUTUBE_CHANNEL_ID", "UCPUS-XlXHCF4PntvyV-WVKg")
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/channels"

    def fetch_stats(self):
        """Fetches subscriber count and total view count for the channel."""
        if not self.api_key:
            return {"error": "API Key missing. Add YOUTUBE_API_KEY to your .env file."}

        params = {
            "part": "statistics",
            "id": self.channel_id,
            "key": self.api_key
        }

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if "items" in data and len(data["items"]) > 0:
                stats = data["items"][0]["statistics"]
                return {
                    "subscribers": stats.get("subscriberCount", "0"),
                    "views": stats.get("viewCount", "0"),
                    "videos": stats.get("videoCount", "0")
                }
            return {"error": "Channel not found."}
        except Exception as e:
            return {"error": str(e)}

    def fetch_recent_videos(self, count=6, page_token=None):
        """Fetches the most recent videos from the channel with pagination support."""
        if not self.api_key:
            return {"error": "API Key missing."}

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": self.channel_id,
            "maxResults": count,
            "order": "date",
            "type": "video",
            "key": self.api_key
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get("items", []):
                snippet = item["snippet"]
                videos.append({
                    "id": item["id"]["videoId"],
                    "title": snippet["title"],
                    "thumbnail": snippet["thumbnails"]["high"]["url"],
                    "published": snippet["publishedAt"]
                })
            return {
                "videos": videos,
                "nextPageToken": data.get("nextPageToken")
            }
        except Exception as e:
            return {"error": str(e)}

    def search_videos(self, query, count=6):
        """Searches for videos within the channel."""
        if not self.api_key:
            return {"error": "API Key missing."}

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": self.channel_id,
            "q": query,
            "maxResults": count,
            "order": "relevance",
            "type": "video",
            "key": self.api_key
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get("items", []):
                snippet = item["snippet"]
                videos.append({
                    "id": item["id"]["videoId"],
                    "title": snippet["title"],
                    "thumbnail": snippet["thumbnails"]["high"]["url"],
                    "published": snippet["publishedAt"]
                })
            return videos
        except Exception as e:
            return {"error": str(e)}

    def format_number(self, num_str):
        """Converts raw numbers to a readable format (e.g., 1190 -> 1.19K)."""
        try:
            num = int(num_str)
            if num >= 1000000:
                return f"{num/1000000:.2f}M"
            if num >= 1000:
                return f"{num/1000:.2f}K"
            return str(num)
        except:
            return num_str

if __name__ == "__main__":
    # Quick test
    yt = YouTubeStats()
    data = yt.fetch_stats()
    if "error" in data:
        print(f"Error: {data['error']}")
    else:
        print(f"Subscribers: {yt.format_number(data['subscribers'])}")
        print(f"Total Views: {yt.format_number(data['views'])}")
