# hejtoscrape

Scrape your [Hejto.pl](https://hejto.pl) profile data and generate a visual stats report.

![Example report for @wombatDaiquiri](example_report.png)

## Features

- Fetches all posts for any public Hejto user via the REST API
- Generates a dark-themed dashboard PNG with:
  - Profile summary (rank, post/comment counts, top posts)
  - Likes & comments per post over time
  - Cumulative likes growth
  - Monthly posting activity
  - Post type breakdown
  - Top 15 tags and top communities
  - Activity by day of week and hour of day
  - Likes distribution histogram
- Caches API responses locally to avoid redundant requests

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Generate a report for a user
python report.py <username>

# Custom output filename
python report.py <username> -o my_report.png

# Force re-fetch from API (ignore cache)
python report.py <username> --refresh
```

## API Client

`hejto_api.py` can be used standalone:

```python
from hejto_api import HejtoAPI

api = HejtoAPI()
profile = api.get_user("wombatDaiquiri")
posts = api.get_all_posts("wombatDaiquiri")
comments = api.get_all_post_comments("some-post-slug")
```

## License

[MIT](LICENSE)
