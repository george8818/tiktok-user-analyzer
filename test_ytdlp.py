"""
Quick test for the yt-dlp scraper. Run from project root:
    python test_ytdlp.py
"""
import asyncio
from src.scraper.ytdlp_scraper import YtDlpScraper

async def main():
    accounts = ["khaby.lame", "zachking", "gordonramsay"]

    scraper = YtDlpScraper(request_delay=2.0)
    async with scraper:
        for username in accounts:
            print(f"\n--- Testing @{username} ---")
            try:
                data = await scraper.scrape_user(username, max_videos=2)
                print(f"  ✅ {data.user.display_name}")
                print(f"     Followers: {data.user.stats.followers:,}")
                print(f"     Videos scraped: {len(data.user.videos)}")
                for v in data.user.videos:
                    print(f"     - {v.description[:60]}...")
                    print(f"       Views: {v.stats.views:,} | Likes: {v.stats.likes:,}")

                # If this works, try the full pipeline:
                print(f"\n  🎯 This account works! Run:")
                print(f"     python -m cli.main analyze @{username} --chat")
                break

            except Exception as e:
                print(f"  ❌ {e}")

asyncio.run(main())
