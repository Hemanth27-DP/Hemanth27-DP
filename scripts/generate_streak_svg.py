#!/usr/bin/env python3
"""
Generate an animated GitHub contribution heatmap SVG (squares light up with a subtle pop/flash).
Uses real scraped data from data/contributions.json.
Usage: python generate_streak_svg.py [username] [output.svg]
"""
import datetime
import json
import os
import sys

DEFAULT_USER = "Hemanth27-DP"
USER = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "svgs", "contrib-heatmap.svg")


def load_contributions_data():
    search_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "contributions.json"),
        "data/contributions.json",
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                print(f"Error reading {p}: {e}", file=sys.stderr)
    return None


def generate_svg(data, out_path):
    if not data or not data.get("days"):
        raise ValueError("No contribution days found in data/contributions.json. Run fetch_contributions.py first.")

    contribs = data["days"]
    total = data.get("total_contributions", 0)
    current_streak = data.get("current_streak", {}).get("length", 0)
    longest_streak = data.get("longest_streak", {}).get("length", 0)

    # Dimensions & Layout
    CELL = 13
    GAP = 3
    RAD = 3
    LEFT = 38
    TOP = 28
    COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
    GRAY = "#7d8590"
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    sd = datetime.date.fromisoformat(contribs[0]["date"])
    start_sunday = sd - datetime.timedelta(days=(sd.weekday() + 1) % 7)
    ed = datetime.date.fromisoformat(contribs[-1]["date"])
    num_weeks = (ed - start_sunday).days // 7 + 1

    width = LEFT + num_weeks * (CELL + GAP) + 12
    height = TOP + 7 * (CELL + GAP) + 38

    reveal_duration = 3.2
    pop_dur = 0.5
    max_order = (num_weeks - 1) + 6 * 0.55

    month_labels = []
    last_m = None
    for wk in range(num_weeks):
        d = start_sunday + datetime.timedelta(days=wk * 7)
        if d.month != last_m:
            last_m = d.month
            month_labels.append(
                f'<text class="lbl" x="{LEFT + wk * (CELL + GAP)}" y="{TOP - 10}">{MONTHS[d.month - 1]}</text>'
            )

    day_labels = []
    for name, r in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
        day_labels.append(
            f'<text class="lbl" x="4" y="{TOP + r * (CELL + GAP) + CELL - 2}">{name}</text>'
        )

    rects = []
    for c in contribs:
        d = datetime.date.fromisoformat(c["date"])
        wk = (d - start_sunday).days // 7
        row = (d.weekday() + 1) % 7
        count = c.get("count", 0)
        level = c.get("level", 0 if count == 0 else min(4, max(1, (count + 2) // 3)))
        if level > 4:
            level = 4

        x = LEFT + wk * (CELL + GAP)
        y = TOP + row * (CELL + GAP)
        delay = round(((wk + row * 0.55) / max_order) * reveal_duration, 3)
        cls = "c g" if level >= 1 else "c e"

        tooltip = f"{count} contribution{'s' if count != 1 else ''} on {c['date']}"
        rects.append(
            f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RAD}" '
            f'fill="{COLORS[level]}" style="animation-delay:{delay}s">'
            f'<title>{tooltip}</title></rect>'
        )

    streak_text = f" • Current streak: {current_streak}d • Longest streak: {longest_streak}d" if longest_streak > 0 else ""

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
  <defs>
    <style>
      .bg {{ fill: #0d1117; }}
      text.lbl {{ fill: {GRAY}; font-size: 11.5px; font-weight: 500; letter-spacing: 0.2px; }}
      text.total {{ fill: #c9d1d9; font-size: 13.5px; font-weight: 600; }}
      text.accent {{ fill: #39d353; font-weight: 700; }}
      text.streak {{ fill: #8b949e; font-size: 12px; font-weight: 500; }}
      .c {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: pop {pop_dur}s ease-out both; }}
      .g {{ animation: pop {pop_dur}s ease-out both, flash {pop_dur + 0.15}s ease-out both; }}
      @keyframes pop {{
        0% {{ opacity: 0; transform: scale(0.2); }}
        60% {{ opacity: 1; transform: scale(1.15); }}
        100% {{ opacity: 1; transform: scale(1); }}
      }}
      @keyframes flash {{
        0% {{ filter: brightness(2.4); }}
        40% {{ filter: brightness(2.4); }}
        100% {{ filter: brightness(1); }}
      }}
      @media (prefers-reduced-motion: reduce) {{
        .c {{ opacity: 1 !important; animation: none !important; }}
      }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" rx="8" class="bg" stroke="#30363d" stroke-width="1"/>
  {''.join(month_labels)}
  {''.join(day_labels)}
  {''.join(rects)}
  <g transform="translate({LEFT}, {height - 12})">
    <text class="total"><tspan class="accent">{total:,}</tspan> contributions in the last year<tspan class="streak">{streak_text}</tspan></text>
  </g>
</svg>'''

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {out_path}: {len(contribs)} days, {total:,} contributions, {len(svg) // 1024} KB")


def main():
    data = load_contributions_data()
    if not data:
        print("Could not load contributions data from data/contributions.json.", file=sys.stderr)
        sys.exit(1)
    generate_svg(data, OUT)


if __name__ == "__main__":
    main()
