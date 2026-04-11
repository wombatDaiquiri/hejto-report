"""Generate a visual report for a Hejto.pl user."""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec

from hejto_api import HejtoAPI

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


def parse_date(iso_str):
    # Handle timezone offset like +02:00
    return datetime.fromisoformat(iso_str)


def generate_report(username, data, output_file="report.png"):
    profile = data["profile"]
    posts = data["posts"]

    if not posts:
        print("No posts found for this user.")
        return

    # Parse post data
    dates = []
    likes = []
    comments = []
    tags_counter = Counter()
    community_counter = Counter()
    weekday_counter = Counter()
    hour_counter = Counter()
    types_counter = Counter()
    monthly_counter = Counter()

    for p in posts:
        dt = parse_date(p["created_at"])
        dates.append(dt)
        likes.append(p.get("num_likes", 0))
        comments.append(p.get("num_comments", 0))
        types_counter[p.get("type", "unknown")] += 1

        for tag in p.get("tags", []):
            tags_counter[tag["name"]] += 1

        community = p.get("community", {})
        if community:
            community_counter[community.get("name", "unknown")] += 1

        weekday_counter[dt.strftime("%A")] += 1
        hour_counter[dt.hour] += 1
        monthly_counter[dt.strftime("%Y-%m")] += 1

    total_likes = sum(likes)
    total_comments = sum(comments)
    avg_likes = total_likes / len(posts)
    avg_comments = total_comments / len(posts)
    max_likes_post = posts[likes.index(max(likes))]
    max_comments_post = posts[comments.index(max(comments))]

    # Sort by date for time series
    sorted_pairs = sorted(zip(dates, likes, comments), key=lambda x: x[0])
    sorted_dates = [x[0] for x in sorted_pairs]
    sorted_likes = [x[1] for x in sorted_pairs]
    sorted_comments = [x[2] for x in sorted_pairs]

    # Cumulative likes over time
    cum_likes = []
    running = 0
    for l in sorted_likes:
        running += l
        cum_likes.append(running)

    # Monthly activity
    months_sorted = sorted(monthly_counter.keys())
    month_counts = [monthly_counter[m] for m in months_sorted]
    month_labels = months_sorted

    # Top tags
    top_tags = tags_counter.most_common(15)

    # Top communities
    top_communities = community_counter.most_common(10)

    # Weekday order
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    weekday_counts = [weekday_counter.get(d, 0) for d in weekday_order]

    # Hour distribution
    hours = list(range(24))
    hour_counts = [hour_counter.get(h, 0) for h in hours]

    # --- PLOTTING ---
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(24, 32))
    fig.patch.set_facecolor("#1a1a2e")

    gs = GridSpec(5, 3, figure=fig, hspace=0.35, wspace=0.3)

    accent = "#e94560"
    accent2 = "#0f3460"
    accent3 = "#16213e"
    highlight = "#f5c518"
    bar_color = "#e94560"
    line_color = "#00d2ff"

    # Title / header
    fig.suptitle(
        f"Hejto.pl Report: @{username}",
        fontsize=28, fontweight="bold", color="white", y=0.98,
    )

    # -- 0: Stats summary box --
    ax_info = fig.add_subplot(gs[0, :])
    ax_info.set_xlim(0, 10)
    ax_info.set_ylim(0, 2)
    ax_info.axis("off")

    rank = profile.get("current_rank", "?")
    member_since = parse_date(profile["created_at"]).strftime("%B %d, %Y")
    n_posts = profile.get("num_posts", len(posts))
    n_comments = profile.get("num_comments", "?")
    n_followers = profile.get("num_follows", "?")
    desc = profile.get("description", "")

    stats_text = (
        f"Rank: {rank}   |   Member since: {member_since}   |   "
        f"Posts: {n_posts}   |   Comments: {n_comments}   |   Followers: {n_followers}\n"
        f'"{desc}"\n\n'
        f"Total likes: {total_likes:,}   |   "
        f"Total comments on posts: {total_comments:,}   |   "
        f"Avg likes/post: {avg_likes:.1f}   |   Avg comments/post: {avg_comments:.1f}\n"
        f"Most liked:      \"{max_likes_post['title'][:70]}\" ({max(likes)} likes)\n"
        f"Most commented:  \"{max_comments_post['title'][:70]}\" ({max(comments)} comments)"
    )
    ax_info.text(
        5, 1, stats_text,
        ha="center", va="center", fontsize=13, color="white",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.8", facecolor=accent3, edgecolor=accent, linewidth=2),
    )

    # -- 1: Likes per post over time (scatter) --
    ax1 = fig.add_subplot(gs[1, 0])
    ax1.scatter(sorted_dates, sorted_likes, s=12, alpha=0.6, c=line_color, edgecolors="none")
    ax1.set_title("Likes per Post (over time)", color="white", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Likes")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # -- 2: Cumulative likes --
    ax2 = fig.add_subplot(gs[1, 1])
    ax2.fill_between(sorted_dates, cum_likes, alpha=0.3, color=accent)
    ax2.plot(sorted_dates, cum_likes, color=accent, linewidth=2)
    ax2.set_title("Cumulative Likes", color="white", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Total Likes")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # -- 3: Comments per post over time --
    ax3 = fig.add_subplot(gs[1, 2])
    ax3.scatter(sorted_dates, sorted_comments, s=12, alpha=0.6, c=highlight, edgecolors="none")
    ax3.set_title("Comments per Post (over time)", color="white", fontsize=12, fontweight="bold")
    ax3.set_ylabel("Comments")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # -- 4: Monthly posting activity --
    ax4 = fig.add_subplot(gs[2, :2])
    x_pos = range(len(month_labels))
    ax4.bar(x_pos, month_counts, color=bar_color, alpha=0.85, edgecolor="none")
    ax4.set_title("Monthly Posting Activity", color="white", fontsize=12, fontweight="bold")
    ax4.set_ylabel("Posts")
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(month_labels, rotation=60, ha="right", fontsize=8)

    # -- 5: Post type distribution --
    ax5 = fig.add_subplot(gs[2, 2])
    type_labels = [t[0] for t in types_counter.most_common()]
    type_sizes = [t[1] for t in types_counter.most_common()]
    colors_pie = [accent, line_color, highlight, "#53d769", "#ff6b6b"]
    ax5.pie(
        type_sizes, labels=type_labels, autopct="%1.0f%%",
        colors=colors_pie[:len(type_labels)],
        textprops={"color": "white", "fontsize": 10},
    )
    ax5.set_title("Post Types", color="white", fontsize=12, fontweight="bold")

    # -- 6: Top tags --
    ax6 = fig.add_subplot(gs[3, :2])
    tag_names = [t[0] for t in reversed(top_tags)]
    tag_counts = [t[1] for t in reversed(top_tags)]
    ax6.barh(tag_names, tag_counts, color=line_color, alpha=0.85)
    ax6.set_title("Top 15 Tags", color="white", fontsize=12, fontweight="bold")
    ax6.set_xlabel("Usage count")

    # -- 7: Top communities --
    ax7 = fig.add_subplot(gs[3, 2])
    comm_names = [c[0] for c in reversed(top_communities)]
    comm_counts = [c[1] for c in reversed(top_communities)]
    ax7.barh(comm_names, comm_counts, color=highlight, alpha=0.85)
    ax7.set_title("Top Communities", color="white", fontsize=12, fontweight="bold")
    ax7.set_xlabel("Posts")

    # -- 8: Weekday activity --
    ax8 = fig.add_subplot(gs[4, 0])
    short_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ax8.bar(short_days, weekday_counts, color=accent, alpha=0.85)
    ax8.set_title("Posts by Day of Week", color="white", fontsize=12, fontweight="bold")
    ax8.set_ylabel("Posts")

    # -- 9: Hour distribution --
    ax9 = fig.add_subplot(gs[4, 1])
    ax9.bar(hours, hour_counts, color=line_color, alpha=0.85)
    ax9.set_title("Posts by Hour of Day", color="white", fontsize=12, fontweight="bold")
    ax9.set_xlabel("Hour")
    ax9.set_ylabel("Posts")
    ax9.xaxis.set_major_locator(ticker.MultipleLocator(2))

    # -- 10: Likes distribution histogram --
    ax10 = fig.add_subplot(gs[4, 2])
    ax10.hist(likes, bins=30, color=accent, alpha=0.85, edgecolor="none")
    ax10.set_title("Likes Distribution", color="white", fontsize=12, fontweight="bold")
    ax10.set_xlabel("Likes")
    ax10.set_ylabel("Frequency")

    # Style all axes
    for ax in fig.get_axes():
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white", labelsize=9)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        for spine in ax.spines.values():
            spine.set_color("#333")

    plt.savefig(output_file, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"\nReport saved to {output_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Generate Hejto.pl user report")
    parser.add_argument("username", help="Hejto username to generate report for")
    parser.add_argument("-o", "--output", default="report.png", help="Output image file")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch data from API")
    args = parser.parse_args()

    data = fetch_and_cache(args.username, force=args.refresh)
    generate_report(args.username, data, output_file=args.output)


if __name__ == "__main__":
    main()
