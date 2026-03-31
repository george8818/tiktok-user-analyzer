"""
Quick scraper test — run this on your local machine to find which accounts work.

Usage:
    python test_scrape.py
"""

import asyncio
import json
import sys

# Accounts to test (mix of sizes, all public)
TEST_ACCOUNTS = [
    "khaby.lame",       # 162M followers, no talking, visual content
    "zachking",         # 82M, magic tricks
    "bellapoarch",     # 94M, music/entertainment
    "charlidamelio",   # 155M, dance
    "addisonre",       # 88M, lifestyle
    "willsmith",       # 76M, comedy
    "gordonramsay",    # 45M, cooking
    "mrbeast",         # 40M, entertainment
    "therock",         # 74M, fitness/entertainment
    "tiktok",          # TikTok official
]


async def test_account(username: str, headless: bool = False) -> dict:
    """Test scraping a single account. Returns result dict."""
    from src.scraper.tiktok_scraper import TikTokScraper, ScraperError

    result = {"username": username, "success": False, "error": None, "data": {}}

    try:
        scraper = TikTokScraper(
            headless=headless,
            timeout=30,
            max_retries=1,
            request_delay=3.0,
        )
        async with scraper:
            data = await scraper.scrape_user(username, max_videos=1)

        result["success"] = True
        result["data"] = {
            "display_name": data.user.display_name,
            "followers": data.user.stats.followers,
            "videos_found": len(data.user.videos),
            "bio": data.user.bio[:50] + "..." if len(data.user.bio) > 50 else data.user.bio,
        }
        print(f"  ✅ @{username}: {data.user.stats.followers:,} followers, "
              f"{len(data.user.videos)} videos scraped")

    except ScraperError as e:
        result["error"] = str(e)
        print(f"  ❌ @{username}: {str(e)[:80]}")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ @{username}: {type(e).__name__}: {str(e)[:60]}")

    return result


async def main():
    headless = "--headless" in sys.argv
    mode = "headless" if headless else "headful (visible browser)"

    print(f"\n{'='*60}")
    print(f"  TikTok Scraper Test — {mode}")
    print(f"  Testing {len(TEST_ACCOUNTS)} accounts...")
    print(f"{'='*60}\n")

    if not headless:
        print("  💡 A Chrome window will open. Don't close it!\n")

    results = []
    for username in TEST_ACCOUNTS:
        r = await test_account(username, headless=headless)
        results.append(r)
        await asyncio.sleep(2)  # Be nice to TikTok

    # Summary
    ok = [r for r in results if r["success"]]
    fail = [r for r in results if not r["success"]]

    print(f"\n{'='*60}")
    print(f"  Results: {len(ok)}/{len(results)} succeeded")
    print(f"{'='*60}")

    if ok:
        print(f"\n  ✅ Working accounts:")
        for r in ok:
            d = r["data"]
            print(f"     @{r['username']}: {d['followers']:,} followers")

        best = max(ok, key=lambda r: r["data"]["videos_found"])
        print(f"\n  🏆 Best account to use for demo: @{best['username']}")
        print(f"     Run: python -m cli.main analyze @{best['username']} {'--headful ' if not headless else ''}--chat")

    if fail:
        print(f"\n  ❌ Failed accounts:")
        for r in fail:
            print(f"     @{r['username']}: {r['error'][:60]}")

    if not ok:
        print(f"\n  ⚠️  All accounts failed. Try:")
        print(f"     1. Run without --headless (visible browser): python test_scrape.py")
        print(f"     2. Use a VPN / different network")
        print(f"     3. Use mock mode: python -m cli.main analyze @khaby.lame --mock --chat")


if __name__ == "__main__":
    print("\n  Options:")
    print("    python test_scrape.py            # headful (recommended)")
    print("    python test_scrape.py --headless  # headless")
    print("")
    asyncio.run(main())
