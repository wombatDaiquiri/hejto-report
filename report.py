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
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
import matplotlib.font_manager as fm
import numpy as np

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
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "axes.titlepad": 14,
        "axes.labelpad": 10,
    })

    # Color palette — soft, modern dark theme
    BG = "#0d1117"          # GitHub-dark inspired background
    CARD = "#161b22"        # Slightly lighter card surfaces
    GRID = "#21262d"        # Subtle grid / spine color
    TEXT = "#e6edf3"        # Primary text (off-white)
    TEXT_DIM = "#8b949e"    # Secondary / muted text
    CYAN = "#58a6ff"        # Primary accent (links / highlights)
    CORAL = "#f78166"       # Warm accent (bars, emphasis)
    GREEN = "#3fb950"       # Success / positive
    PURPLE = "#bc8cff"      # Tertiary accent
    YELLOW = "#d29922"      # Attention / highlight
    PINK = "#f778ba"        # Pie / extra accent

    fig = plt.figure(figsize=(24, 34))
    fig.patch.set_facecolor(BG)

    gs = GridSpec(
        5, 6, figure=fig,
        hspace=0.42, wspace=0.38,
        top=0.90, bottom=0.03, left=0.06, right=0.97,
    )

    def style_ax(ax, title="", ylabel="", xlabel="", grid_axis="y"):
        """Apply consistent modern styling to an axes."""
        ax.set_facecolor(CARD)
        ax.set_title(title, color=TEXT, fontsize=13, fontweight="600", loc="left")
        if ylabel:
            ax.set_ylabel(ylabel, color=TEXT_DIM, fontsize=10)
        if xlabel:
            ax.set_xlabel(xlabel, color=TEXT_DIM, fontsize=10)
        ax.tick_params(colors=TEXT_DIM, labelsize=9, length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if grid_axis:
            ax.grid(axis=grid_axis, color=GRID, linewidth=0.6, alpha=0.7)
            ax.set_axisbelow(True)

    # ── Header ──────────────────────────────────────────────
    fig.text(
        0.06, 0.975, f"@{username}",
        fontsize=36, fontweight="bold", color=TEXT,
        va="top",
    )
    fig.text(
        0.06, 0.963, "hejto.pl user report",
        fontsize=14, color=TEXT_DIM, va="top",
    )
    fig.text(
        0.97, 0.975,
        "github.com/wombatDaiquiri/hejto-report",
        fontsize=10, color=TEXT_DIM, va="top", ha="right",
        style="italic",
    )

    # ── Row 0: KPI cards ───────────────────────────────────
    rank = profile.get("current_rank", "?")
    member_since = parse_date(profile["created_at"]).strftime("%b %d, %Y")
    n_posts = profile.get("num_posts", len(posts))
    n_comments_profile = profile.get("num_comments", "?")
    n_followers = profile.get("num_follows", "?")
    desc = profile.get("description", "")

    kpi_data = [
        ("Posts", f"{n_posts:,}" if isinstance(n_posts, int) else str(n_posts)),
        ("Total Likes", f"{total_likes:,}"),
        ("Comments Received", f"{total_comments:,}"),
        ("Avg Likes / Post", f"{avg_likes:.1f}"),
        ("Avg Comments / Post", f"{avg_comments:.1f}"),
        ("Followers", f"{n_followers:,}" if isinstance(n_followers, int) else str(n_followers)),
    ]

    for i, (label, value) in enumerate(kpi_data):
        ax = fig.add_subplot(gs[0, i])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_facecolor(CARD)
        # Card background
        card = plt.Rectangle((0.03, 0.05), 0.94, 0.9, transform=ax.transAxes,
                              facecolor=CARD, edgecolor=GRID, linewidth=1.2,
                              clip_on=False, zorder=0)
        card.set_path_effects([pe.withSimplePatchShadow(offset=(1, -1), shadow_rgbFace=BG, alpha=0.5)])
        ax.add_patch(card)
        ax.text(0.5, 0.62, value, transform=ax.transAxes,
                ha="center", va="center", fontsize=22, fontweight="bold", color=CYAN)
        ax.text(0.5, 0.28, label, transform=ax.transAxes,
                ha="center", va="center", fontsize=10, color=TEXT_DIM)

    # ── Profile info strip (figure-level text, no grid row) ──
    info_parts = [
        f"Rank: {rank}",
        f"Member since: {member_since}",
    ]
    if desc:
        info_parts.append(f'"{desc[:120]}"')
    info_line = "    \u2022    ".join(info_parts)

    record_line = (
        f"Most liked: \"{max_likes_post['title'][:65]}\" ({max(likes)} likes)    \u2022    "
        f"Most commented: \"{max_comments_post['title'][:65]}\" ({max(comments)} comments)"
    )

    fig.text(0.515, 0.925, info_line, ha="center", va="center", fontsize=11, color=TEXT_DIM)
    fig.text(0.515, 0.912, record_line, ha="center", va="center", fontsize=10, color=TEXT_DIM, style="italic")

    # ── Row 1: Time series ─────────────────────────────────
    # Likes scatter
    ax1 = fig.add_subplot(gs[1, :2])
    ax1.scatter(sorted_dates, sorted_likes, s=14, alpha=0.55, c=CYAN, edgecolors="none", zorder=3)
    # Trend line
    if len(sorted_dates) > 10:
        x_num = mdates.date2num(sorted_dates)
        z = np.polyfit(x_num, sorted_likes, 1)
        p = np.poly1d(z)
        ax1.plot(sorted_dates, p(x_num), color=CORAL, linewidth=1.8, alpha=0.7, linestyle="--", zorder=4)
    style_ax(ax1, title="Likes per Post Over Time", ylabel="Likes")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=40, ha="right")

    # Cumulative likes
    ax2 = fig.add_subplot(gs[1, 2:4])
    ax2.fill_between(sorted_dates, cum_likes, alpha=0.15, color=CYAN)
    ax2.plot(sorted_dates, cum_likes, color=CYAN, linewidth=2.2)
    style_ax(ax2, title="Cumulative Likes", ylabel="Total Likes")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=40, ha="right")

    # Comments scatter
    ax3 = fig.add_subplot(gs[1, 4:])
    ax3.scatter(sorted_dates, sorted_comments, s=14, alpha=0.55, c=YELLOW, edgecolors="none", zorder=3)
    if len(sorted_dates) > 10:
        z2 = np.polyfit(x_num, sorted_comments, 1)
        p2 = np.poly1d(z2)
        ax3.plot(sorted_dates, p2(x_num), color=CORAL, linewidth=1.8, alpha=0.7, linestyle="--", zorder=4)
    style_ax(ax3, title="Comments per Post Over Time", ylabel="Comments")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=40, ha="right")

    # ── Row 3: Monthly activity + Post types ───────────────
    ax4 = fig.add_subplot(gs[2, :4])
    x_pos = range(len(month_labels))
    bars = ax4.bar(x_pos, month_counts, color=CYAN, alpha=0.80, edgecolor="none", width=0.75, zorder=3)
    # Highlight peak month
    if month_counts:
        peak_idx = month_counts.index(max(month_counts))
        bars[peak_idx].set_color(CORAL)
        bars[peak_idx].set_alpha(0.95)
    style_ax(ax4, title="Monthly Posting Activity", ylabel="Posts")
    ax4.set_xticks(x_pos)
    # Show every Nth label to avoid crowding
    n_months = len(month_labels)
    step = max(1, n_months // 18)
    ax4.set_xticklabels(
        [m if i % step == 0 else "" for i, m in enumerate(month_labels)],
        rotation=45, ha="right", fontsize=8,
    )

    # Post type — donut chart
    ax5 = fig.add_subplot(gs[2, 4:])
    type_labels = [t[0] for t in types_counter.most_common()]
    type_sizes = [t[1] for t in types_counter.most_common()]
    colors_pie = [CYAN, CORAL, YELLOW, GREEN, PINK, PURPLE]
    wedges, texts, autotexts = ax5.pie(
        type_sizes, labels=type_labels, autopct="%1.0f%%",
        colors=colors_pie[:len(type_labels)],
        textprops={"color": TEXT, "fontsize": 10},
        pctdistance=0.78,
        wedgeprops=dict(width=0.45, edgecolor=CARD, linewidth=2),
        startangle=90,
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight("bold")
        at.set_color(TEXT)
    ax5.set_facecolor(CARD)
    ax5.set_title("Post Types", color=TEXT, fontsize=13, fontweight="600", loc="left", pad=14)

    # ── Row 4: Tags + Communities ──────────────────────────
    ax6 = fig.add_subplot(gs[3, :4])
    tag_names = [t[0] for t in reversed(top_tags)]
    tag_counts_list = [t[1] for t in reversed(top_tags)]
    tag_bars = ax6.barh(tag_names, tag_counts_list, color=CYAN, alpha=0.80, height=0.65, zorder=3)
    # Value labels at end of bars
    for bar, val in zip(tag_bars, tag_counts_list):
        ax6.text(bar.get_width() + max(tag_counts_list) * 0.015, bar.get_y() + bar.get_height() / 2,
                 str(val), va="center", fontsize=9, color=TEXT_DIM)
    style_ax(ax6, title="Top 15 Tags", xlabel="Usage count", grid_axis="x")

    ax7 = fig.add_subplot(gs[3, 4:])
    comm_names = [c[0] for c in reversed(top_communities)]
    comm_counts_list = [c[1] for c in reversed(top_communities)]
    comm_bars = ax7.barh(comm_names, comm_counts_list, color=PURPLE, alpha=0.80, height=0.65, zorder=3)
    for bar, val in zip(comm_bars, comm_counts_list):
        ax7.text(bar.get_width() + max(comm_counts_list) * 0.02, bar.get_y() + bar.get_height() / 2,
                 str(val), va="center", fontsize=9, color=TEXT_DIM)
    style_ax(ax7, title="Top Communities", xlabel="Posts", grid_axis="x")

    # ── Row 5: Weekday, Hourly, Likes histogram ───────────
    ax8 = fig.add_subplot(gs[4, :2])
    short_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_colors = [CORAL if v == max(weekday_counts) else CYAN for v in weekday_counts]
    ax8.bar(short_days, weekday_counts, color=day_colors, alpha=0.80, width=0.6, zorder=3)
    style_ax(ax8, title="Posts by Day of Week", ylabel="Posts")

    ax9 = fig.add_subplot(gs[4, 2:4])
    hour_colors = [CORAL if v == max(hour_counts) else CYAN for v in hour_counts]
    ax9.bar(hours, hour_counts, color=hour_colors, alpha=0.80, width=0.75, zorder=3)
    style_ax(ax9, title="Posts by Hour of Day", xlabel="Hour (24h)", ylabel="Posts")
    ax9.xaxis.set_major_locator(ticker.MultipleLocator(2))

    ax10 = fig.add_subplot(gs[4, 4:])
    ax10.hist(likes, bins=30, color=CYAN, alpha=0.80, edgecolor=CARD, linewidth=0.8, zorder=3)
    style_ax(ax10, title="Likes Distribution", xlabel="Likes", ylabel="Frequency")

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
