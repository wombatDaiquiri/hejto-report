"""Generate an interactive HTML report for a Hejto.pl user."""

import json
import html
from collections import Counter
from datetime import datetime


def parse_date(iso_str):
    return datetime.fromisoformat(iso_str)


def generate_html_report(username, data, output_file="report.html", png_mode=False):
    profile = data["profile"]
    posts = data["posts"]

    if not posts:
        print("No posts found for this user.")
        return

    # Parse post data
    dates = []
    likes = []
    comments = []
    slugs = []
    titles = []
    tags_counter = Counter()
    community_counter = Counter()
    weekday_counter = Counter()
    hour_counter = Counter()
    hour_likes = {}  # hour -> list of like counts
    types_counter = Counter()
    monthly_counter = Counter()

    for p in posts:
        dt = parse_date(p["created_at"])
        dates.append(dt)
        likes.append(p.get("num_likes", 0))
        comments.append(p.get("num_comments", 0))
        slugs.append(p.get("slug", ""))
        titles.append(p.get("title", ""))
        types_counter[p.get("type", "unknown")] += 1

        for tag in p.get("tags", []):
            tags_counter[tag["name"]] += 1

        community = p.get("community", {})
        if community:
            community_counter[community.get("name", "unknown")] += 1

        weekday_counter[dt.strftime("%A")] += 1
        hour_counter[dt.hour] += 1
        hour_likes.setdefault(dt.hour, []).append(p.get("num_likes", 0))
        monthly_counter[dt.strftime("%Y-%m")] += 1

    total_likes = sum(likes)
    total_comments = sum(comments)
    avg_likes = total_likes / len(posts)
    avg_comments = total_comments / len(posts)

    # Sort by date for time series
    sorted_pairs = sorted(
        zip(dates, likes, comments, slugs, titles), key=lambda x: x[0]
    )
    sorted_dates = [x[0].isoformat() for x in sorted_pairs]
    sorted_likes = [x[1] for x in sorted_pairs]
    sorted_comments = [x[2] for x in sorted_pairs]
    sorted_slugs = [x[3] for x in sorted_pairs]
    sorted_titles = [x[4] for x in sorted_pairs]

    # Cumulative likes
    cum_likes = []
    running = 0
    for l in sorted_likes:
        running += l
        cum_likes.append(running)

    # Monthly activity
    months_sorted = sorted(monthly_counter.keys())
    month_counts = [monthly_counter[m] for m in months_sorted]

    # Top tags
    top_tags = tags_counter.most_common(15)
    tag_names = [t[0] for t in top_tags]
    tag_counts = [t[1] for t in top_tags]

    # Top communities
    top_communities = community_counter.most_common(10)
    comm_names = [c[0] for c in top_communities]
    comm_counts = [c[1] for c in top_communities]

    # Weekday
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    short_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_counts = [weekday_counter.get(d, 0) for d in weekday_order]

    # Hours
    hours = list(range(24))
    hour_counts = [hour_counter.get(h, 0) for h in hours]

    # Average likes per hour
    avg_likes_by_hour = [
        round(sum(hour_likes.get(h, [0])) / max(len(hour_likes.get(h, [0])), 1), 1)
        for h in hours
    ]

    # Post types
    type_labels = [t[0] for t in types_counter.most_common()]
    type_sizes = [t[1] for t in types_counter.most_common()]

    # Likes distribution (histogram bins)
    max_like = max(likes) if likes else 1

    # Top posts by likes
    posts_by_likes = sorted(
        zip(likes, comments, titles, slugs, dates),
        key=lambda x: x[0], reverse=True
    )[:20]

    # Top posts by comments
    posts_by_comments = sorted(
        zip(comments, likes, titles, slugs, dates),
        key=lambda x: x[0], reverse=True
    )[:20]

    # Profile info
    rank = profile.get("current_rank", "?")
    member_since = parse_date(profile["created_at"]).strftime("%b %d, %Y")
    n_posts = profile.get("num_posts", len(posts))
    n_followers = profile.get("num_follows", "?")
    desc = profile.get("description", "")
    avatar_urls = profile.get("avatar", {}).get("urls", {})
    avatar_url = avatar_urls.get("250x250") or avatar_urls.get("100x100") or ""

    # Build hover text with links for scatter plots
    hover_texts_likes = []
    hover_texts_comments = []
    custom_data = []
    for i in range(len(sorted_dates)):
        dt_str = parse_date(sorted_dates[i]).strftime("%b %d, %Y %H:%M")
        title_short = sorted_titles[i][:80] if sorted_titles[i] else "(no title)"
        hover_texts_likes.append(
            f"<b>{html.escape(title_short)}</b><br>"
            f"Date: {dt_str}<br>"
            f"Likes: {sorted_likes[i]}<br>"
            f"Comments: {sorted_comments[i]}"
        )
        hover_texts_comments.append(
            f"<b>{html.escape(title_short)}</b><br>"
            f"Date: {dt_str}<br>"
            f"Comments: {sorted_comments[i]}<br>"
            f"Likes: {sorted_likes[i]}"
        )
        custom_data.append(sorted_slugs[i])

    # Reverse order so largest is on top in horizontal bar charts
    tag_names_rev = list(reversed(tag_names))
    tag_counts_rev = list(reversed(tag_counts))
    comm_names_rev = list(reversed(comm_names))
    comm_counts_rev = list(reversed(comm_counts))

    # Serialize data for JS
    chart_data = json.dumps({
        "sorted_dates": sorted_dates,
        "sorted_likes": sorted_likes,
        "sorted_comments": sorted_comments,
        "sorted_slugs": sorted_slugs,
        "sorted_titles": sorted_titles,
        "hover_likes": hover_texts_likes,
        "hover_comments": hover_texts_comments,
        "cum_likes": cum_likes,
        "months": months_sorted,
        "month_counts": month_counts,
        "tag_names": tag_names_rev,
        "tag_counts": tag_counts_rev,
        "comm_names": comm_names_rev,
        "comm_counts": comm_counts_rev,
        "short_days": short_days,
        "weekday_counts": weekday_counts,
        "hours": hours,
        "hour_counts": hour_counts,
        "avg_likes_by_hour": avg_likes_by_hour,
        "type_labels": type_labels,
        "type_sizes": type_sizes,
        "all_likes": likes,
    })

    def post_url(slug):
        return f"https://www.hejto.pl/wpis/{slug}"

    def make_table_rows(items, primary_label, secondary_label):
        rows = []
        for i, item in enumerate(items):
            primary_val, secondary_val, title, slug, dt = item
            dt_str = dt.strftime("%b %d, %Y")
            title_esc = html.escape(title[:100]) if title else "(no title)"
            url = post_url(slug)
            rows.append(
                f'<tr>'
                f'<td>{i+1}</td>'
                f'<td><a href="{url}" target="_blank">{title_esc}</a></td>'
                f'<td>{primary_val}</td>'
                f'<td>{secondary_val}</td>'
                f'<td>{dt_str}</td>'
                f'</tr>'
            )
        return "\n".join(rows)

    top_likes_rows = make_table_rows(posts_by_likes, "Likes", "Comments")
    top_comments_rows = make_table_rows(posts_by_comments, "Comments", "Likes")

    desc_html = f'<span class="desc">"{html.escape(desc[:150])}"</span>' if desc else ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hejto Report - @{html.escape(username)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  :root {{
    --bg: #0d1117;
    --card: #161b22;
    --grid: #21262d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --cyan: #58a6ff;
    --coral: #f78166;
    --green: #3fb950;
    --purple: #bc8cff;
    --yellow: #d29922;
    --pink: #f778ba;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .header {{
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 12px;
  }}
  .avatar {{
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--grid);
  }}
  .header-text h1 {{
    font-size: 32px;
    font-weight: 700;
  }}
  .header-text .meta {{
    color: var(--text-dim);
    font-size: 14px;
    margin-top: 4px;
  }}
  .header-text .desc {{
    color: var(--text-dim);
    font-style: italic;
  }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin: 20px 0 28px;
  }}
  .kpi-card {{
    background: var(--card);
    border: 1px solid var(--grid);
    border-radius: 10px;
    padding: 18px 14px;
    text-align: center;
  }}
  .kpi-card .value {{
    font-size: 28px;
    font-weight: 700;
    color: var(--cyan);
  }}
  .kpi-card .label {{
    font-size: 13px;
    color: var(--text-dim);
    margin-top: 6px;
  }}
  .chart-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }}
  .chart-grid.triple {{
    grid-template-columns: 1fr 1fr 1fr;
  }}
  .chart-box {{
    background: var(--card);
    border: 1px solid var(--grid);
    border-radius: 10px;
    padding: 8px;
    min-height: 350px;
  }}
  .chart-box.wide {{
    grid-column: span 2;
  }}
  .chart-box.full {{
    grid-column: 1 / -1;
  }}
  h2 {{
    font-size: 18px;
    font-weight: 600;
    margin: 32px 0 14px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--grid);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 24px;
  }}
  th, td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--grid);
    font-size: 14px;
  }}
  th {{
    background: var(--grid);
    color: var(--text-dim);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  td:first-child {{ width: 40px; color: var(--text-dim); text-align: center; }}
  td:nth-child(3), td:nth-child(4) {{ text-align: right; width: 90px; }}
  td:last-child {{ width: 110px; color: var(--text-dim); }}
  a {{ color: var(--cyan); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{
    text-align: center;
    color: var(--text-dim);
    font-size: 12px;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid var(--grid);
  }}
  @media (max-width: 900px) {{
    .chart-grid, .chart-grid.triple {{ grid-template-columns: 1fr; }}
    .chart-box.wide {{ grid-column: span 1; }}
  }}
</style>
</head>
<body>

<div class="header">
  {"<img class='avatar' src='" + html.escape(avatar_url) + "' alt='avatar'>" if avatar_url else ""}
  <div class="header-text">
    <h1>@{html.escape(username)}</h1>
    <div class="meta">
      Rank: {html.escape(str(rank))} &bull; Member since: {member_since} &bull; {desc_html}
    </div>
  </div>
</div>

<div class="kpi-row">
  <div class="kpi-card"><div class="value">{n_posts:,}</div><div class="label">Posts</div></div>
  <div class="kpi-card"><div class="value">{total_likes:,}</div><div class="label">Total Likes</div></div>
  <div class="kpi-card"><div class="value">{total_comments:,}</div><div class="label">Comments Received</div></div>
  <div class="kpi-card"><div class="value">{avg_likes:.1f}</div><div class="label">Avg Likes / Post</div></div>
  <div class="kpi-card"><div class="value">{avg_comments:.1f}</div><div class="label">Avg Comments / Post</div></div>
  <div class="kpi-card"><div class="value">{n_followers:,}</div><div class="label">Followers</div></div>
</div>

<div class="chart-grid">
  <div class="chart-box" id="likes-scatter"></div>
  <div class="chart-box" id="comments-scatter"></div>
  <div class="chart-box" id="cum-likes"></div>
  <div class="chart-box" id="monthly"></div>
</div>

<div class="chart-grid">
  <div class="chart-box" id="tags"></div>
  <div class="chart-box" id="communities"></div>
</div>

<div class="chart-grid triple">
  <div class="chart-box" id="weekday"></div>
  <div class="chart-box" id="hourly"></div>
  <div class="chart-box" id="likes-dist"></div>
</div>

<div class="chart-grid">
  <div class="chart-box full" id="likes-by-hour"></div>
</div>

{"" if png_mode else f"""<h2>Top Posts by Likes</h2>
<table>
  <thead><tr><th>#</th><th>Title</th><th>Likes</th><th>Comments</th><th>Date</th></tr></thead>
  <tbody>{top_likes_rows}</tbody>
</table>

<h2>Top Posts by Comments</h2>
<table>
  <thead><tr><th>#</th><th>Title</th><th>Comments</th><th>Likes</th><th>Date</th></tr></thead>
  <tbody>{top_comments_rows}</tbody>
</table>"""}

<div class="footer">
  Generated by <a href="https://github.com/wombatDaiquiri/hejto-report">hejto-report</a>
</div>

<script>
const D = {chart_data};
const BASE_URL = "https://www.hejto.pl/wpis/";
const layout = {{
  paper_bgcolor: '#161b22',
  plot_bgcolor: '#161b22',
  font: {{ color: '#e6edf3', family: 'Segoe UI, Helvetica Neue, Arial, sans-serif', size: 12 }},
  margin: {{ t: 40, b: 50, l: 55, r: 20 }},
  xaxis: {{ gridcolor: '#21262d', zerolinecolor: '#21262d' }},
  yaxis: {{ gridcolor: '#21262d', zerolinecolor: '#21262d' }},
  hoverlabel: {{ bgcolor: '#1c2129', bordercolor: '#30363d', font: {{ color: '#e6edf3', size: 13 }} }},
}};
const config = {{ responsive: true, displayModeBar: false }};

function clickToPost(plotId) {{
  document.getElementById(plotId).on('plotly_click', function(ev) {{
    const idx = ev.points[0].pointIndex;
    const slug = D.sorted_slugs[idx];
    if (slug) window.open(BASE_URL + slug, '_blank');
  }});
}}

// Likes scatter
Plotly.newPlot('likes-scatter', [{{
  x: D.sorted_dates, y: D.sorted_likes,
  customdata: D.sorted_slugs,
  text: D.hover_likes,
  hoverinfo: 'text',
  mode: 'markers',
  marker: {{ color: '#58a6ff', size: 6, opacity: 0.6 }},
  type: 'scatter',
}}], {{
  ...layout,
  title: {{ text: 'Likes per Post Over Time', font: {{ size: 15 }} }},
  yaxis: {{ ...layout.yaxis, title: 'Likes' }},
}}, config);
clickToPost('likes-scatter');

// Comments scatter
Plotly.newPlot('comments-scatter', [{{
  x: D.sorted_dates, y: D.sorted_comments,
  customdata: D.sorted_slugs,
  text: D.hover_comments,
  hoverinfo: 'text',
  mode: 'markers',
  marker: {{ color: '#d29922', size: 6, opacity: 0.6 }},
  type: 'scatter',
}}], {{
  ...layout,
  title: {{ text: 'Comments per Post Over Time', font: {{ size: 15 }} }},
  yaxis: {{ ...layout.yaxis, title: 'Comments' }},
}}, config);
clickToPost('comments-scatter');

// Cumulative likes
Plotly.newPlot('cum-likes', [{{
  x: D.sorted_dates, y: D.cum_likes,
  text: D.cum_likes.map((v, i) => `Cumulative: ${{v.toLocaleString()}}<br>Post likes: ${{D.sorted_likes[i]}}`),
  hoverinfo: 'text+x',
  fill: 'tozeroy',
  fillcolor: 'rgba(88,166,255,0.12)',
  line: {{ color: '#58a6ff', width: 2 }},
  type: 'scatter',
}}], {{
  ...layout,
  title: {{ text: 'Cumulative Likes', font: {{ size: 15 }} }},
  yaxis: {{ ...layout.yaxis, title: 'Total Likes' }},
}}, config);

// Monthly activity
const peakMonth = Math.max(...D.month_counts);
Plotly.newPlot('monthly', [{{
  x: D.months, y: D.month_counts,
  text: D.month_counts.map(String),
  hoverinfo: 'x+text',
  type: 'bar',
  marker: {{ color: D.month_counts.map(v => v === peakMonth ? '#f78166' : '#58a6ff'), opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Monthly Posting Activity', font: {{ size: 15 }} }},
  yaxis: {{ ...layout.yaxis, title: 'Posts' }},
  xaxis: {{ ...layout.xaxis, tickangle: -45 }},
}}, config);

// Top tags (horizontal bar)
Plotly.newPlot('tags', [{{
  y: D.tag_names, x: D.tag_counts,
  text: D.tag_counts.map(String),
  textposition: 'outside',
  hoverinfo: 'y+text',
  type: 'bar',
  orientation: 'h',
  marker: {{ color: '#58a6ff', opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Top 15 Tags', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, title: 'Usage count', type: 'linear' }},
  yaxis: {{ ...layout.yaxis, categoryorder: 'array', categoryarray: D.tag_names }},
  margin: {{ ...layout.margin, l: 130, r: 55 }},
}}, config);

// Top communities
Plotly.newPlot('communities', [{{
  y: D.comm_names, x: D.comm_counts,
  text: D.comm_counts.map(String),
  textposition: 'outside',
  hoverinfo: 'y+text',
  type: 'bar',
  orientation: 'h',
  marker: {{ color: '#bc8cff', opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Top Communities', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, title: 'Posts', type: 'linear' }},
  yaxis: {{ ...layout.yaxis, categoryorder: 'array', categoryarray: D.comm_names }},
  margin: {{ ...layout.margin, l: 130, r: 55 }},
}}, config);

// Weekday
const peakDay = Math.max(...D.weekday_counts);
Plotly.newPlot('weekday', [{{
  x: D.short_days, y: D.weekday_counts,
  text: D.weekday_counts.map(String),
  hoverinfo: 'x+text',
  type: 'bar',
  marker: {{ color: D.weekday_counts.map(v => v === peakDay ? '#f78166' : '#58a6ff'), opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Posts by Day of Week', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, type: 'category' }},
  yaxis: {{ ...layout.yaxis, title: 'Posts' }},
}}, config);

// Hourly
const peakHour = Math.max(...D.hour_counts);
Plotly.newPlot('hourly', [{{
  x: D.hours, y: D.hour_counts,
  text: D.hour_counts.map(String),
  hoverinfo: 'x+text',
  type: 'bar',
  marker: {{ color: D.hour_counts.map(v => v === peakHour ? '#f78166' : '#58a6ff'), opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Posts by Hour of Day', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, title: 'Hour (24h)', type: 'linear', dtick: 2 }},
  yaxis: {{ ...layout.yaxis, title: 'Posts' }},
}}, config);

// Likes distribution
Plotly.newPlot('likes-dist', [{{
  x: D.all_likes,
  type: 'histogram',
  nbinsx: 30,
  marker: {{ color: '#58a6ff', opacity: 0.85, line: {{ color: '#161b22', width: 1 }} }},
  hovertemplate: 'Likes: %{{x}}<br>Count: %{{y}}<extra></extra>',
}}], {{
  ...layout,
  title: {{ text: 'Likes Distribution', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, title: 'Likes', type: 'linear' }},
  yaxis: {{ ...layout.yaxis, title: 'Frequency' }},
}}, config);

// Average likes by hour of day
const peakAvgHour = Math.max(...D.avg_likes_by_hour);
Plotly.newPlot('likes-by-hour', [{{
  x: D.hours, y: D.avg_likes_by_hour,
  text: D.avg_likes_by_hour.map(v => v.toString()),
  hovertemplate: 'Hour: %{{x}}:00<br>Avg likes: %{{y}}<extra></extra>',
  type: 'bar',
  marker: {{ color: D.avg_likes_by_hour.map(v => v === peakAvgHour ? '#f78166' : '#3fb950'), opacity: 0.85 }},
}}], {{
  ...layout,
  title: {{ text: 'Average Likes by Hour of Day', font: {{ size: 15 }} }},
  xaxis: {{ ...layout.xaxis, title: 'Hour (24h)', type: 'linear', dtick: 1 }},
  yaxis: {{ ...layout.yaxis, title: 'Avg Likes' }},
}}, config);
</script>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\nInteractive HTML report saved to {output_file}")
