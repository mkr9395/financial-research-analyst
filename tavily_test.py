from dotenv import load_dotenv
from tavily import TavilyClient
import os

load_dotenv()

api_key = os.getenv("TAVILY_API_KEY")

if not api_key:
    print("❌ TAVILY_API_KEY was not found")
    exit()

print("✅ TAVILY_API_KEY was loaded")

client = TavilyClient(api_key=api_key)

response = client.search(
    query="latest developments in generative AI",
    max_results=3
)

print("✅ Tavily API is working")
print("\nSearch results:")

for result in response["results"]:
    print("\nTitle:", result["title"])
    print("URL:", result["url"])