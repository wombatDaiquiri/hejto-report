"""Hejto.pl API client for fetching user data, posts, and comments."""

import time
import requests

BASE_URL = "https://api.hejto.pl"


class HejtoAPI:
    def __init__(self, rate_limit_delay=0.25):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.rate_limit_delay = rate_limit_delay

    def _get(self, path, params=None):
        time.sleep(self.rate_limit_delay)
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_user(self, username):
        """Fetch user profile."""
        return self._get(f"/users/{username}")

    def get_posts(self, username, page=1, limit=50):
        """Fetch posts by a user. Max limit per page is 50."""
        params = {
            "users[]": username,
            "orderBy": "p.createdAt",
            "orderDir": "desc",
            "period": "all",
            "page": page,
            "limit": limit,
        }
        return self._get("/posts", params=params)

    def get_all_posts(self, username, progress_callback=None):
        """Fetch all posts by a user, handling pagination."""
        all_posts = []
        page = 1
        while True:
            data = self.get_posts(username, page=page, limit=50)
            items = data.get("_embedded", {}).get("items", [])
            if not items:
                break
            all_posts.extend(items)
            total_pages = data.get("pages", 1)
            if progress_callback:
                progress_callback(page, total_pages, len(all_posts))
            if page >= total_pages:
                break
            page += 1
        return all_posts

    def get_post_comments(self, post_slug, page=1, limit=50):
        """Fetch comments on a specific post."""
        params = {"page": page, "limit": limit}
        return self._get(f"/posts/{post_slug}/comments", params=params)

    def get_all_post_comments(self, post_slug):
        """Fetch all comments on a specific post."""
        all_comments = []
        page = 1
        while True:
            data = self.get_post_comments(post_slug, page=page, limit=50)
            items = data.get("_embedded", {}).get("items", [])
            if not items:
                break
            all_comments.extend(items)
            if page >= data.get("pages", 1):
                break
            page += 1
        return all_comments
