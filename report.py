"""Generate a visual report for a Hejto.pl user."""

import argparse
import json
import os
import tempfile
from datetime import datetime

from hejto_api import HejtoAPI
from report_html import generate_html_report

CACHE_DIR = "cache"


def cache_path(username):
    return os.path.join(CACHE_DIR, f"{username}_posts.json")


def fetch_and_cache(username, force=False):
    """Fetch all posts and cache to disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = cache_path(username)
    if not force and os.path.exists(path):
        print(f"Using cached data from {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    api = HejtoAPI()
    print(f"Fetching profile for @{username}...")
    profile = api.get_user(username)

    def progress(page, total, count):
        print(f"  Fetching posts: page {page}/{total} ({count} posts so far)")

    print("Fetching all posts...")
    posts = api.get_all_posts(username, progress_callback=progress)
    print(f"Fetched {len(posts)} posts total.")

    data = {"profile": profile, "posts": posts}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def generate_png_report(username, data, output_file="report.png"):
    """Generate HTML report, then render it to PNG via Playwright."""
    from playwright.sync_api import sync_playwright

    # Generate HTML to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=".")
    tmp_path = tmp.name
    tmp.close()

    try:
        generate_html_report(username, data, output_file=tmp_path, png_mode=True)

        abs_path = os.path.abspath(tmp_path)
        file_url = "file:///" + abs_path.replace("\\", "/")

        print("Rendering PNG...")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(file_url, wait_until="networkidle")

            # Wait for all Plotly charts to finish rendering
            page.wait_for_function("""
                () => {
                    const ids = ['likes-scatter', 'comments-scatter', 'cum-likes',
                                 'monthly', 'tags', 'communities',
                                 'weekday', 'hourly', 'likes-dist'];
                    return ids.every(id => {
                        const el = document.getElementById(id);
                        return el && el.data && el.data.length > 0;
                    });
                }
            """, timeout=30000)

            # Get full page height
            height = page.evaluate("document.body.scrollHeight")
            page.set_viewport_size({"width": 1400, "height": height})
            # Small delay for re-layout after resize
            page.wait_for_timeout(500)

            page.screenshot(path=output_file, full_page=True)
            browser.close()

        print(f"\nReport saved to {output_file}")
    finally:
        os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(description="Generate Hejto.pl user report")
    parser.add_argument("username", help="Hejto username to generate report for")
    parser.add_argument("-o", "--output", default="report.png", help="Output file (.png or .html)")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch data from API")
    parser.add_argument("--html", action="store_true", help="Generate interactive HTML report")
    args = parser.parse_args()

    data = fetch_and_cache(args.username, force=args.refresh)

    output = args.output
    if args.html and not output.endswith(".html"):
        output = output.rsplit(".", 1)[0] + ".html"

    if output.endswith(".html") or args.html:
        generate_html_report(args.username, data, output_file=output)
    else:
        generate_png_report(args.username, data, output_file=output)


if __name__ == "__main__":
    main()
