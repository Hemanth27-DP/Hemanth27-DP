#!/usr/bin/env python3
"""
Scrape real daily contribution counts from GitHub's public contributions endpoint
and write data/contributions.json with raw days plus derived metrics:
(total contributions, active days, current streak, longest streak, best day, monthly totals).

No token, no auth required -- uses the public HTML fragment GitHub serves for the profile.
Automated by .github/workflows/update-profile-art.yml.
"""
import datetime
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

DEFAULT_USERNAME = "Hemanth27-DP"
USERNAME = os.environ.get("GH_PROFILE_USER", DEFAULT_USERNAME)
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "contributions.json")


def fetch_calendar_html(username):
    """Fetch the contribution calendar fragment, trying the username as-is and without trailing hyphen if 404."""
    candidates = [username]
    if username.endswith("-"):
        candidates.append(username.rstrip("-"))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    last_err = None
    for user in candidates:
        url = f"https://github.com/users/{user}/contributions"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and "ContributionCalendar-day" in resp.text:
                return user, resp.text
            elif resp.status_code != 404:
                resp.raise_for_status()
        except Exception as e:
            last_err = e

    if last_err:
        raise last_err
    raise RuntimeError(f"Could not retrieve contribution calendar for candidates: {candidates}")


def parse_days(soup):
    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        raise ValueError("No calendar cells found -- GitHub markup structure may have changed")

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0

        level_str = td.get("data-level", "0")
        try:
            level = int(level_str)
        except ValueError:
            level = 0
        days.append({"date": date, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])
    return days


def compute_current_streak(days):
    if not days:
        return 0, None, None
    idx = len(days) - 1
    # If today has 0 contributions, don't break the active streak just because today hasn't ended yet
    if days[idx]["count"] == 0:
        idx -= 1
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(active_user, days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": None, "count": 0, "level": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": active_user,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {
            "start": days[0]["date"] if days else None,
            "end": days[-1]["date"] if days else None,
        },
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"], "level": best.get("level", 0)},
        "monthly": monthly_list,
        "days": days,
    }


def main():
    try:
        active_user, html = fetch_calendar_html(USERNAME)
        soup = BeautifulSoup(html, "html.parser")
        days = parse_days(soup)
        data = build_data(active_user, days)

        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(
            f"Successfully updated {OUT_PATH} for {active_user}: "
            f"{data['total_contributions']} contributions, "
            f"{data['active_days']} active days, "
            f"current streak {data['current_streak']['length']}, "
            f"longest streak {data['longest_streak']['length']}"
        )
    except Exception as e:
        print(f"Error fetching contributions from GitHub: {e}", file=sys.stderr)
        if os.path.exists(OUT_PATH):
            print(f"Using existing cached data at {OUT_PATH}", file=sys.stderr)
            sys.exit(0)
        else:
            print("No cached contributions data found; failing clearly without generating fake data.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
