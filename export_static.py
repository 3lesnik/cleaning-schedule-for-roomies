#!/usr/bin/env python3
"""
Static Site & Calendar Generator for GitHub Pages

Generates a static `docs/` folder containing:
- `docs/index.html`: Main landing page and directory of roommate calendar links.
- `docs/calendars/<person>.ics`: Static calendar files for direct subscription.
- `docs/c/<person>.html`: Mobile-friendly personal calendar page for each roommate.
- `docs/.nojekyll`: Disables Jekyll processing on GitHub Pages.
"""

import os
import shutil
import datetime
import json
from schedule_manager import ScheduleManager

DOCS_DIR = "docs"

def get_task_icon(task):
    t = task.lower()
    if "kitchen" in t:
        return "🍳"
    elif "bath" in t:
        return "🚿"
    elif "toilet" in t or "wc" in t:
        return "🚽"
    elif "trash" in t or "bin" in t or "recycling" in t:
        return "🗑️"
    elif "floor" in t or "hallway" in t or "stairs" in t:
        return "🧹"
    elif "laundry" in t:
        return "🧺"
    return "✨"

def get_person_gradient(person):
    gradients = [
        "from-blue-600 to-indigo-600",
        "from-emerald-600 to-teal-600",
        "from-purple-600 to-pink-600",
        "from-amber-500 to-orange-600",
        "from-rose-500 to-red-600",
        "from-cyan-600 to-blue-600",
    ]
    h = sum(ord(c) for c in person)
    return gradients[h % len(gradients)]

def get_waste_pill_class(waste_type):
    if "Organic" in waste_type:
        return "bg-emerald-100 text-emerald-800 border-emerald-300"
    elif "Residual" in waste_type:
        return "bg-blue-100 text-blue-800 border-blue-300"
    elif "Paper" in waste_type:
        return "bg-amber-100 text-amber-800 border-amber-300"
    elif "Chemical" in waste_type:
        return "bg-purple-100 text-purple-800 border-purple-300"
    return "bg-slate-100 text-slate-800 border-slate-300"


def generate_docs(manager=None):
    if manager is None:
        manager = ScheduleManager()
        
    os.makedirs(DOCS_DIR, exist_ok=True)
    calendars_dir = os.path.join(DOCS_DIR, "calendars")
    c_dir = os.path.join(DOCS_DIR, "c")
    os.makedirs(calendars_dir, exist_ok=True)
    os.makedirs(c_dir, exist_ok=True)

    # 1. Create .nojekyll
    with open(os.path.join(DOCS_DIR, ".nojekyll"), "w") as f:
        f.write("")

    manager.refresh_task_schedules()
    people = manager.data.get("people", [])
    weeks = manager.data.get("weeks", [])
    house_events = manager.data.get("house_events", [])
    tasks = manager.data.get("tasks", [])

    # 2. Export individual .ics files
    for person in people:
        ical_bytes = manager.generate_ical_for_person(person)
        ics_path = os.path.join(calendars_dir, f"{person}.ics")
        with open(ics_path, "wb") as f:
            f.write(ical_bytes)

    # 3. Export individual roommate HTML pages
    for person in people:
        cleanings = []
        trash_pickups = []
        
        for w in weeks:
            for task, p in w["assignments"].items():
                if p == person:
                    date_str, time_str, is_ovr = manager.compute_task_schedule(w, task, person)
                    d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    cleanings.append({
                        "week": w["week_number"],
                        "date": date_str,
                        "day_name": d.strftime("%A"),
                        "time": time_str,
                        "task": task
                    })
            for tp in w.get("trash_pickups", []):
                if tp.get("assigned_to") == person:
                    rem_date_str = tp.get("reminder_date") or tp["date"]
                    rem_d = datetime.datetime.strptime(rem_date_str, "%Y-%m-%d")
                    trash_pickups.append({
                        "reminder_date": rem_date_str,
                        "reminder_day": rem_d.strftime("%A"),
                        "reminder_time": tp.get("reminder_time", "20:00"),
                        "pickup_date": tp.get("pickup_date") or tp["date"],
                        "waste_type": tp["waste_type"],
                        "title": tp.get("title") or f"Put out the {tp['waste_type']}"
                    })

        my_house_events = [he for he in house_events if he.get("target_audience") in ["all", person]]

        c_html_path = os.path.join(c_dir, f"{person}.html")
        with open(c_html_path, "w") as f:
            f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{person}'s Calendar & Schedule</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .waste-Organic {{ background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }}
        .waste-Residual {{ background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }}
        .waste-Paper {{ background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }}
        .waste-Chemical {{ background-color: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; }}
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen pb-16">
    <div id="toast" class="fixed bottom-6 right-6 z-50 transform transition-all duration-300 translate-y-20 opacity-0 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm font-medium">
        <span>📋</span>
        <span id="toast-message">Calendar feed link copied!</span>
    </div>

    <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href="../index.html" class="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center space-x-1">
                <span>&larr;</span>
                <span>Full House Schedule</span>
            </a>
            <span class="text-xs text-slate-400 font-medium">Apartment Calendar Sync</span>
        </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div class="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-xs space-y-6">
            <div class="flex items-center space-x-4">
                <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center text-3xl font-bold shadow-md">
                    {person[0]}
                </div>
                <div>
                    <h1 class="text-2xl md:text-3xl font-extrabold text-slate-900">{person}'s Schedule</h1>
                    <p class="text-xs md:text-sm text-slate-500">Live calendar with cleaning duties, trash pickups & house events</p>
                </div>
            </div>

            <div class="bg-slate-50 rounded-xl p-4 md:p-5 border border-slate-200 space-y-3">
                <div class="text-xs font-bold uppercase tracking-wider text-slate-500">Subscribe & Sync With Your Calendar</div>
                <div class="flex flex-wrap gap-2.5">
                    <a id="webcal-btn" href="#" class="inline-flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition">
                        <span>📲</span>
                        <span>Subscribe in Calendar (Apple/iOS/Mac/Outlook)</span>
                    </a>
                    <button onclick="copyFeedUrl()" class="inline-flex items-center space-x-2 px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl border border-slate-300 shadow-xs transition">
                        <span>📋</span>
                        <span>Copy Feed URL (Google Calendar)</span>
                    </button>
                </div>
                <div class="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 pt-1 border-t border-slate-200/60">
                    <div>
                        <strong>Google Calendar:</strong> Click Copy Feed URL &rarr; Go to <a href="https://calendar.google.com/calendar/r/settings/addbyurl" target="_blank" class="text-blue-600 underline">Google Calendar &gt; Add Calendar &gt; From URL</a> &rarr; Paste link.
                    </div>
                    <a href="../calendars/{person}.ics" download="cleaning_schedule_{person}.ics" class="text-slate-400 hover:text-slate-600 underline">
                        Download raw .ics
                    </a>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <!-- Cleaning Chores -->
            <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
                <h2 class="text-sm font-bold text-slate-900 flex items-center space-x-1.5 border-b border-slate-100 pb-3">
                    <span>🧹</span>
                    <span>Duties ({len(cleanings)})</span>
                </h2>
                <div class="space-y-2.5 max-h-96 overflow-y-auto pr-1">
""")
            if cleanings:
                for c in cleanings:
                    time_badge = f'<div class="text-[11px] text-slate-500">⏰ Scheduled at {c["time"]}</div>' if c.get("time") else ''
                    f.write(f"""                    <div class="p-3 rounded-xl border border-slate-100 bg-slate-50/50 text-xs space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-slate-800">{c['day_name']}, {c['date']}</span>
                            <span class="text-slate-400 font-mono text-[11px]">Week {c['week']}</span>
                        </div>
                        <div class="font-semibold text-blue-700">{c['task']}</div>
                        {time_badge}
                    </div>\n""")
            else:
                f.write("""                    <p class="text-xs text-slate-400 py-4 text-center">No chores assigned.</p>\n""")

            f.write(f"""                </div>
            </div>

            <!-- Trash Duties -->
            <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
                <h2 class="text-sm font-bold text-slate-900 flex items-center space-x-1.5 border-b border-slate-100 pb-3">
                    <span>🗑️</span>
                    <span>Trash Duties ({len(trash_pickups)})</span>
                </h2>
                <div class="space-y-2.5 max-h-96 overflow-y-auto pr-1">
""")
            if trash_pickups:
                for tp in trash_pickups:
                    waste_cls = "bg-slate-100"
                    if "Organic" in tp["waste_type"]: waste_cls = "waste-Organic"
                    elif "Residual" in tp["waste_type"]: waste_cls = "waste-Residual"
                    elif "Paper" in tp["waste_type"]: waste_cls = "waste-Paper"
                    elif "Chemical" in tp["waste_type"]: waste_cls = "waste-Chemical"

                    f.write(f"""                    <div class="p-3 rounded-xl border border-slate-100 bg-slate-50/50 text-xs space-y-1.5">
                        <div class="font-bold text-slate-800 flex items-center justify-between">
                            <span>{tp['title']}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-semibold {waste_cls}">
                                {tp['waste_type']}
                            </span>
                        </div>
                        <div class="text-[11px] text-purple-700 font-medium">
                            ⏰ {tp['reminder_day']}, {tp['reminder_date']} at 8:00 PM
                        </div>
                        <div class="text-[10px] text-slate-400">
                            Pickup is tomorrow, {tp['pickup_date']}
                        </div>
                    </div>\n""")
            else:
                f.write("""                    <p class="text-xs text-slate-400 py-4 text-center">No trash pickups assigned.</p>\n""")

            f.write(f"""                </div>
            </div>

            <!-- House Events -->
            <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
                <h2 class="text-sm font-bold text-slate-900 flex items-center space-x-1.5 border-b border-slate-100 pb-3">
                    <span>🏠</span>
                    <span>House Events ({len(my_house_events)})</span>
                </h2>
                <div class="space-y-2.5 max-h-96 overflow-y-auto pr-1">
""")
            if my_house_events:
                for he in my_house_events:
                    time_info = f'<div class="text-[11px] text-purple-700 font-medium">⏰ {he["time"]}</div>' if he.get("time") else ""
                    desc_info = f'<p class="text-[11px] text-slate-600 pt-0.5">{he["description"]}</p>' if he.get("description") else ""
                    f.write(f"""                    <div class="p-3 rounded-xl border border-purple-100 bg-purple-50/30 text-xs space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-purple-900">{he['title']}</span>
                            <span class="text-purple-600 font-mono text-[11px]">{he['date']}</span>
                        </div>
                        {time_info}
                        {desc_info}
                    </div>\n""")
            else:
                f.write("""                    <p class="text-xs text-slate-400 py-4 text-center">No house events scheduled.</p>\n""")

            f.write(f"""                </div>
            </div>
        </div>
    </main>

    <script>
        const icsRelativeUrl = new URL("../calendars/{person}.ics", window.location.href).href;
        const webcalUrl = icsRelativeUrl.replace(/^https?:\/\//i, 'webcal://');
        document.getElementById('webcal-btn').href = webcalUrl;

        function copyFeedUrl() {{
            navigator.clipboard.writeText(icsRelativeUrl).then(() => {{
                showToast('Calendar feed URL copied to clipboard!');
            }}).catch(() => {{
                prompt('Copy this calendar feed URL:', icsRelativeUrl);
            }});
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toast');
            document.getElementById('toast-message').textContent = msg;
            toast.classList.remove('translate-y-20', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
            setTimeout(() => {{
                toast.classList.add('translate-y-20', 'opacity-0');
                toast.classList.remove('translate-y-0', 'opacity-100');
            }}, 3000);
        }}
    </script>
</body>
</html>""")

    # 4. Export Main `docs/index.html` (Public Hub)
    # Determine default active week (today)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    active_week_idx = 0
    for i, w in enumerate(weeks):
        if w.get("start_date", "") <= today_str <= w.get("end_date", ""):
            active_week_idx = i
            break
        elif today_str > w.get("end_date", ""):
            active_week_idx = i

    current_week = weeks[active_week_idx] if weeks else None

    # Prepare JSON bundle for client-side interactions
    hub_json_data = json.dumps({
        "weeks": weeks,
        "tasks": tasks,
        "people": people,
        "house_events": house_events,
        "active_week_idx": active_week_idx,
        "today_str": today_str
    })

    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apartment Cleaning & Trash Schedules</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .waste-Organic {{ background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }}
        .waste-Residual {{ background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }}
        .waste-Paper {{ background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }}
        .waste-Chemical {{ background-color: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; }}
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen flex flex-col">

    <!-- Toast Notification -->
    <div id="toast" class="fixed bottom-6 right-6 z-50 transform transition-all duration-300 translate-y-20 opacity-0 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm font-medium">
        <span>📋</span>
        <span id="toast-message">Calendar feed URL copied!</span>
    </div>

    <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <span class="text-3xl">🧹</span>
                <div>
                    <h1 class="text-xl font-bold text-slate-900 leading-tight">Apartment Cleaning & Trash Hub</h1>
                    <p class="text-xs text-slate-500">Live calendar subscriptions & hosted schedule overview</p>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <a href="#weekly-overview" class="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition">
                    <span>📅</span>
                    <span>This Week</span>
                </a>
                <a href="#roommate-calendars" class="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition">
                    <span>📲</span>
                    <span>Subscribe</span>
                </a>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8 flex-1 w-full space-y-8">
        
        <!-- SECTION 1: Current Week's Schedule & Trash Overview -->
        <section id="weekly-overview" class="bg-white rounded-2xl border border-slate-200 p-5 md:p-6 shadow-xs space-y-6">
            <!-- Header Bar -->
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-100 pb-5">
                <div class="space-y-1">
                    <div class="flex items-center space-x-2.5 flex-wrap">
                        <span class="text-2xl">📅</span>
                        <h2 id="hub-week-title" class="text-xl md:text-2xl font-black text-slate-900">
                            Week {current_week['week_number'] if current_week else 1} Overview
                        </h2>
                        <span id="hub-week-badge" class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                            ✨ Active This Week
                        </span>
                    </div>
                    <p id="hub-week-dates" class="text-xs md:text-sm text-slate-500 font-medium">
                        {current_week['start_date'] if current_week else ''} &rarr; {current_week['end_date'] if current_week else ''}
                    </p>
                </div>

                <!-- Week Navigator Toolbar -->
                <div class="flex items-center flex-wrap gap-2">
                    <button id="btn-prev-week" onclick="changeHubWeek(-1)" class="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-bold rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition">
                        <span>◀</span>
                        <span>Prev</span>
                    </button>
                    <select id="hub-week-select" onchange="onHubWeekSelect(this.value)" class="text-xs font-bold border border-slate-300 rounded-xl px-3 py-1.5 bg-white text-slate-800 shadow-xs focus:ring-2 focus:ring-blue-500">
""")
        for idx, w in enumerate(weeks):
            is_cur = (idx == active_week_idx)
            sel_attr = ' selected' if is_cur else ''
            f.write(f"""                        <option value="{idx}"{sel_attr}>Week {w['week_number']} ({w['start_date'][5:]} &rarr; {w['end_date'][5:]}){' • This Week' if is_cur else ''}</option>\n""")

        f.write(f"""                    </select>
                    <button id="btn-next-week" onclick="changeHubWeek(1)" class="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-bold rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition">
                        <span>Next</span>
                        <span>▶</span>
                    </button>
                    <button id="btn-today-week" onclick="resetToCurrentWeek()" class="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-bold rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 shadow-xs transition" title="Jump to today's active week">
                        <span>📍</span>
                        <span>This Week</span>
                    </button>
                </div>
            </div>

            <!-- Cleaning Chores Grid -->
            <div class="space-y-3">
                <div class="flex items-center justify-between">
                    <h3 class="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center space-x-1.5">
                        <span>🧹</span>
                        <span>Cleaning Chores ({len(tasks)})</span>
                    </h3>
                    <span class="text-[11px] text-slate-400">Click roommate for personal calendar link</span>
                </div>

                <div id="hub-chores-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
""")
        # Pre-render current week chores
        if current_week:
            for task in tasks:
                person = current_week["assignments"].get(task, "Unassigned")
                sched = current_week.get("task_schedules", {}).get(task, {})
                icon = get_task_icon(task)
                grad = get_person_gradient(person)
                day_name = sched.get("day_name", "")
                date_val = sched.get("date", current_week.get("start_date"))
                time_val = sched.get("time")
                is_ovr = sched.get("is_override", False)

                time_display = f'<span class="text-slate-400">•</span> ⏰ at {time_val}' if time_val else ''
                ovr_badge = '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-1.5 py-0.5 rounded" title="Custom override for this week">Custom</span>' if is_ovr else ''

                f.write(f"""                    <div class="bg-slate-50/70 hover:bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex items-center justify-between transition">
                        <div class="flex items-center space-x-3 min-w-0">
                            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr {grad} text-white flex items-center justify-center font-bold text-base shadow-xs shrink-0">
                                {person[0]}
                            </div>
                            <div class="min-w-0">
                                <div class="flex items-center space-x-1.5">
                                    <span class="text-sm">{icon}</span>
                                    <span class="text-xs font-bold text-slate-800 truncate">{task}</span>
                                    {ovr_badge}
                                </div>
                                <div class="text-sm font-bold text-slate-900 mt-0.5">
                                    <a href="c/{person}.html" class="hover:text-blue-600 hover:underline">
                                        {person}
                                    </a>
                                </div>
                                <div class="text-[11px] text-slate-500 font-medium">
                                    {day_name}, {date_val} {time_display}
                                </div>
                            </div>
                        </div>
                        <a href="c/{person}.html" class="text-slate-400 hover:text-blue-600 p-1.5 rounded-lg hover:bg-blue-50 transition text-xs shrink-0" title="View {person}'s schedule">
                            &rarr;
                        </a>
                    </div>\n""")

        f.write(f"""                </div>
            </div>

            <!-- Trash Duties for Selected Week -->
            <div class="space-y-3 pt-2 border-t border-slate-100">
                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center space-x-1.5">
                    <span>🗑️</span>
                    <span>Trash Duties This Week</span>
                </h3>
                <div id="hub-trash-container" class="space-y-2">
""")
        # Pre-render current week trash pickups
        week_pickups = current_week.get("trash_pickups", []) if current_week else []
        if week_pickups:
            for tp in week_pickups:
                waste_pill = get_waste_pill_class(tp["waste_type"])
                f.write(f"""                    <div class="bg-slate-50 rounded-xl border border-slate-200 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-start sm:items-center space-x-3">
                            <span class="text-2xl shrink-0">🗑️</span>
                            <div>
                                <div class="flex items-center flex-wrap gap-1.5">
                                    <span class="text-xs font-bold text-slate-900">{tp.get('title', 'Put out the ' + tp['waste_type'])}</span>
                                    <span class="px-2 py-0.5 text-[10px] font-bold rounded-md border {waste_pill}">
                                        {tp['waste_type']}
                                    </span>
                                </div>
                                <div class="text-xs text-purple-800 font-semibold mt-0.5">
                                    ⏰ Put out bins: <strong>{tp.get('reminder_date', tp['date'])} at {tp.get('reminder_time', '20:00')}</strong> (Pickup: {tp.get('pickup_date', tp['date'])})
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center space-x-2 shrink-0">
                            <span class="text-xs text-slate-500">Assigned to:</span>
                            <a href="c/{tp.get('assigned_to')}.html" class="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-xs font-bold text-slate-800 hover:border-blue-400 hover:text-blue-600 transition">
                                <span>👤</span>
                                <span>{tp.get('assigned_to')}</span>
                            </a>
                        </div>
                    </div>\n""")
        else:
            f.write("""                    <div class="bg-slate-50 rounded-xl border border-dashed border-slate-200 p-3 text-center text-xs text-slate-500">
                        ✅ No special trash bin pickups scheduled for this week.
                    </div>\n""")

        # House events for this week
        week_start_str = current_week.get("start_date", "") if current_week else ""
        week_end_str = current_week.get("end_date", "") if current_week else ""
        cur_house_events = [he for he in house_events if week_start_str <= he.get("date", "") <= week_end_str]
        cur_he_hidden_cls = "" if cur_house_events else " hidden"

        f.write(f"""                </div>
            </div>

            <!-- House Events for Selected Week -->
            <div id="hub-house-events-wrapper" class="space-y-3 pt-2 border-t border-slate-100{cur_he_hidden_cls}">
                <h3 class="text-xs font-bold uppercase tracking-wider text-purple-800 flex items-center space-x-1.5">
                    <span>🏠</span>
                    <span>House Events This Week</span>
                </h3>
                <div id="hub-house-events-container" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
""")
        for he in cur_house_events:
            time_display = f'<div class="text-[11px] text-slate-600 font-medium">⏰ at {he["time"]}</div>' if he.get("time") else '<div class="text-[11px] text-slate-500">(All day)</div>'
            desc_display = f'<p class="text-[11px] text-slate-600 pt-0.5">{he["description"]}</p>' if he.get("description") else ''
            f.write(f"""                    <div class="bg-purple-50/60 border border-purple-200 rounded-xl p-3 text-xs space-y-1">
                        <div class="flex items-center justify-between font-bold text-purple-900">
                            <span>{he['title']}</span>
                            <span class="font-mono text-[11px] text-purple-600">{he['date']}</span>
                        </div>
                        {time_display}
                        {desc_display}
                    </div>\n""")

        f.write(f"""                </div>
            </div>

            <!-- Collapsible Full Rotation Table -->
            <div class="pt-2 border-t border-slate-100">
                <button onclick="toggleHubRotationTable()" id="btn-toggle-rotation-table" class="w-full py-2.5 px-4 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-bold rounded-xl border border-slate-200 transition flex items-center justify-between">
                    <span class="flex items-center space-x-2">
                        <span>📊</span>
                        <span>View Full {len(weeks)}-Week Rotation Matrix</span>
                    </span>
                    <span id="rotation-toggle-arrow" class="text-slate-400 font-mono">▼ Show Table</span>
                </button>

                <div id="hub-rotation-table-wrapper" class="hidden mt-4 overflow-x-auto rounded-xl border border-slate-200">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="bg-slate-50 text-slate-600 border-b border-slate-200 text-[11px] uppercase tracking-wider">
                                <th class="py-2.5 px-3 font-bold">Week</th>
                                <th class="py-2.5 px-3 font-bold">Dates</th>
""")
        for task in tasks:
            f.write(f"""                                <th class="py-2.5 px-3 font-bold">{task}</th>\n""")

        f.write(f"""                            </tr>
                        </thead>
                        <tbody id="hub-rotation-tbody" class="divide-y divide-slate-100">
""")
        for idx, w in enumerate(weeks):
            is_cur = (idx == active_week_idx)
            row_cls = "bg-blue-50/90 font-bold border-l-4 border-l-blue-600 text-blue-950 transition cursor-pointer" if is_cur else "hover:bg-slate-50/80 transition cursor-pointer"
            badge_cur = ' <span class="ml-1 text-[10px] bg-emerald-100 text-emerald-800 font-bold px-1.5 py-0.2 rounded-full">Active</span>' if is_cur else ''
            f.write(f"""                            <tr id="hub-rot-row-{idx}" class="{row_cls}" onclick="renderHubWeek({idx})">
                                <td class="py-2 px-3 font-bold whitespace-nowrap">Week {w['week_number']}{badge_cur}</td>
                                <td class="py-2 px-3 text-slate-500 whitespace-nowrap text-[11px]">{w['start_date'][5:]} &rarr; {w['end_date'][5:]}</td>\n""")
            for task in tasks:
                assignee = w["assignments"].get(task, "-")
                f.write(f"""                                <td class="py-2 px-3 whitespace-nowrap font-medium text-slate-700">{assignee}</td>\n""")
            f.write("""                            </tr>\n""")

        f.write(f"""                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- SECTION 2: Roommate Cards Directory -->
        <div id="roommate-calendars">
            <h2 class="text-lg font-bold text-slate-900 mb-1">Roommate Calendars & Personal Links</h2>
            <p class="text-xs text-slate-500 mb-4">Click <strong>Subscribe</strong> to sync automatically with your phone or laptop calendar.</p>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
""")
        for person in people:
            grad = get_person_gradient(person)
            f.write(f"""                <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:shadow-md transition space-y-4 flex flex-col justify-between">
                    <div class="space-y-3">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                                <div class="w-12 h-12 rounded-xl bg-gradient-to-tr {grad} text-white flex items-center justify-center text-xl font-bold shadow-xs">
                                    {person[0]}
                                </div>
                                <div>
                                    <h3 class="text-base font-bold text-slate-900">{person}</h3>
                                    <span class="inline-flex items-center text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">Live Sync Feed</span>
                                </div>
                            </div>
                            <a href="c/{person}.html" class="text-xs font-semibold text-blue-600 hover:text-blue-800 p-1.5 hover:bg-blue-50 rounded-lg transition" title="View Full Schedule">
                                Details &rarr;
                            </a>
                        </div>
                        <p class="text-xs text-slate-500">Includes weekly cleaning chores, 8:00 PM day-before trash alerts & house events.</p>
                    </div>

                    <div class="space-y-2 pt-3 border-t border-slate-100">
                        <div class="flex items-center space-x-2">
                            <a data-webcal-person="{person}" href="#" class="flex-1 inline-flex items-center justify-center space-x-1.5 py-2.5 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition" title="Subscribe in Apple Calendar, iOS or Outlook">
                                <span>📲</span>
                                <span>Subscribe</span>
                            </a>
                            <button onclick="copyPersonFeed('{person}')" class="inline-flex items-center justify-center space-x-1 py-2.5 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition" title="Copy URL for Google Calendar">
                                <span>📋</span>
                                <span>Copy URL</span>
                            </button>
                        </div>
                        <div class="flex items-center justify-between px-1 text-[11px] text-slate-400">
                            <a href="c/{person}.html" class="hover:text-slate-600">View Schedule &rarr;</a>
                            <a href="calendars/{person}.ics" download="cleaning_schedule_{person}.ics" class="hover:text-slate-600 underline">Download raw .ics</a>
                        </div>
                    </div>
                </div>\n""")

        f.write(f"""            </div>
        </div>

        <!-- SECTION 3: House Events Banner (if any) -->
""")
        if house_events:
            f.write("""        <div class="bg-purple-50 rounded-2xl border border-purple-200 p-6 space-y-3">
            <h2 class="text-base font-bold text-purple-950 flex items-center space-x-2">
                <span>🏠</span>
                <span>Upcoming House Events</span>
            </h2>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
""")
            for he in house_events:
                time_str = f" at {he['time']}" if he.get('time') else " (All day)"
                f.write(f"""                <div class="bg-white p-3.5 rounded-xl border border-purple-100 shadow-xs text-xs space-y-1">
                    <div class="flex items-center justify-between font-bold text-purple-900">
                        <span>{he['title']}</span>
                        <span class="font-mono text-[11px] text-purple-600">{he['date']}</span>
                    </div>
                    <div class="text-[11px] text-slate-500">{time_str}</div>
                    {f'<p class="text-[11px] text-slate-600 pt-0.5">{he["description"]}</p>' if he.get("description") else ''}
                </div>\n""")
            f.write("""            </div>
        </div>\n""")

        f.write(f"""        <!-- SECTION 4: How to Subscribe Guide -->
        <div id="subscribe-guide" class="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4 scroll-mt-20">
            <h2 class="text-base font-bold text-slate-900">How to Subscribe to Your Calendar</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600">
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <h3 class="font-bold text-slate-900">📱 iPhone / Apple Calendar / Mac</h3>
                    <p>Click <strong>"Subscribe"</strong> on your card. iOS/macOS will open Calendar automatically with a prompt to subscribe.</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <h3 class="font-bold text-slate-900">📅 Google Calendar</h3>
                    <p>Click <strong>"Copy URL"</strong>. Go to Google Calendar &gt; Other calendars (+) &gt; <strong>From URL</strong> &gt; Paste the link.</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <h3 class="font-bold text-slate-900">🔄 Auto-Updates</h3>
                    <p>Once subscribed, your calendar automatically syncs chores, trash days, and house events whenever the schedule updates!</p>
                </div>
            </div>
        </div>

    </main>

    <footer class="text-center py-6 text-xs text-slate-400 border-t border-slate-200 bg-white">
        Apartment Cleaning & Trash Schedule • Hosted via GitHub Pages
    </footer>

    <!-- Embedded Schedule Data for Client-side Navigation -->
    <script id="hub-schedule-data" type="application/json">
{hub_json_data}
    </script>

    <script>
        // Setup webcal URLs
        document.querySelectorAll('[data-webcal-person]').forEach(el => {{
            const person = el.getAttribute('data-webcal-person');
            const icsUrl = new URL(`calendars/${{encodeURIComponent(person)}}.ics`, window.location.href).href;
            el.href = icsUrl.replace(/^https?:\\/\\//i, 'webcal://');
        }});

        function copyPersonFeed(person) {{
            const icsUrl = new URL(`calendars/${{encodeURIComponent(person)}}.ics`, window.location.href).href;
            navigator.clipboard.writeText(icsUrl).then(() => {{
                showToast(`${{person}}'s calendar subscription URL copied!`);
            }}).catch(() => {{
                prompt(`Copy ${{person}}'s calendar URL:`, icsUrl);
            }});
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toast');
            document.getElementById('toast-message').textContent = msg;
            toast.classList.remove('translate-y-20', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
            setTimeout(() => {{
                toast.classList.add('translate-y-20', 'opacity-0');
                toast.classList.remove('translate-y-0', 'opacity-100');
            }}, 3000);
        }}

        // Hub Interactive Logic
        const hubDataEl = document.getElementById('hub-schedule-data');
        const HUB = hubDataEl ? JSON.parse(hubDataEl.textContent) : null;
        let activeCalendarWeekIdx = HUB ? HUB.active_week_idx : 0;
        let currentViewWeekIdx = activeCalendarWeekIdx;

        function getTaskIcon(task) {{
            const t = task.toLowerCase();
            if (t.includes('kitchen')) return '🍳';
            if (t.includes('bath')) return '🚿';
            if (t.includes('toilet') || t.includes('wc')) return '🚽';
            if (t.includes('trash') || t.includes('bin') || t.includes('recycling')) return '🗑️';
            if (t.includes('floor') || t.includes('hallway') || t.includes('stairs')) return '🧹';
            if (t.includes('laundry')) return '🧺';
            return '✨';
        }}

        function getPersonGradient(person) {{
            const gradients = [
                "from-blue-600 to-indigo-600",
                "from-emerald-600 to-teal-600",
                "from-purple-600 to-pink-600",
                "from-amber-500 to-orange-600",
                "from-rose-500 to-red-600",
                "from-cyan-600 to-blue-600",
            ];
            let h = 0;
            for (let i = 0; i < person.length; i++) h += person.charCodeAt(i);
            return gradients[h % gradients.length];
        }}

        function getWastePillClass(wasteType) {{
            if (wasteType.includes("Organic")) return "bg-emerald-100 text-emerald-800 border-emerald-300";
            if (wasteType.includes("Residual")) return "bg-blue-100 text-blue-800 border-blue-300";
            if (wasteType.includes("Paper")) return "bg-amber-100 text-amber-800 border-amber-300";
            if (wasteType.includes("Chemical")) return "bg-purple-100 text-purple-800 border-purple-300";
            return "bg-slate-100 text-slate-800 border-slate-300";
        }}

        function initHub() {{
            if (!HUB || !HUB.weeks || HUB.weeks.length === 0) return;

            // Automatically check today's date against weeks in client browser
            const today = new Date().toISOString().slice(0, 10);
            for (let i = 0; i < HUB.weeks.length; i++) {{
                const w = HUB.weeks[i];
                if (today >= w.start_date && today <= w.end_date) {{
                    activeCalendarWeekIdx = i;
                    currentViewWeekIdx = i;
                    break;
                }} else if (today > w.end_date) {{
                    activeCalendarWeekIdx = i;
                    currentViewWeekIdx = i;
                }}
            }}
            if (today < HUB.weeks[0].start_date) {{
                activeCalendarWeekIdx = 0;
                currentViewWeekIdx = 0;
            }}

            renderHubWeek(currentViewWeekIdx);
        }}

        function renderHubWeek(idx) {{
            if (!HUB || !HUB.weeks || idx < 0 || idx >= HUB.weeks.length) return;
            currentViewWeekIdx = idx;
            const week = HUB.weeks[idx];

            const select = document.getElementById('hub-week-select');
            if (select) select.value = idx;

            const btnPrev = document.getElementById('btn-prev-week');
            const btnNext = document.getElementById('btn-next-week');
            if (btnPrev) btnPrev.disabled = (idx === 0);
            if (btnNext) btnNext.disabled = (idx === HUB.weeks.length - 1);

            document.getElementById('hub-week-title').textContent = `Week ${{week.week_number}} Overview`;
            document.getElementById('hub-week-dates').innerHTML = `${{week.start_date}} &rarr; ${{week.end_date}}`;

            const badge = document.getElementById('hub-week-badge');
            if (idx === activeCalendarWeekIdx) {{
                badge.className = "px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300";
                badge.textContent = "✨ Active This Week";
            }} else if (idx < activeCalendarWeekIdx) {{
                badge.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-600 border border-slate-300";
                badge.textContent = "Past Week";
            }} else {{
                badge.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-50 text-blue-700 border border-blue-200";
                badge.textContent = "Upcoming Week";
            }}

            // Render Chores Grid
            const grid = document.getElementById('hub-chores-grid');
            grid.innerHTML = '';
            HUB.tasks.forEach(task => {{
                const person = week.assignments[task] || 'Unassigned';
                const sched = (week.task_schedules && week.task_schedules[task]) ? week.task_schedules[task] : null;
                const icon = getTaskIcon(task);
                const grad = getPersonGradient(person);

                let dayDate = week.start_date;
                let timeInfo = '';
                let isOvr = false;
                if (sched) {{
                    dayDate = `${{sched.day_name || ''}}, ${{sched.date}}`;
                    if (sched.time) timeInfo = `<span class="text-slate-400">•</span> ⏰ at ${{sched.time}}`;
                    isOvr = sched.is_override;
                }}

                const card = document.createElement('div');
                card.className = "bg-slate-50/70 hover:bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex items-center justify-between transition";
                card.innerHTML = `
                    <div class="flex items-center space-x-3 min-w-0">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr ${{grad}} text-white flex items-center justify-center font-bold text-base shadow-xs shrink-0">
                            ${{person[0]}}
                        </div>
                        <div class="min-w-0">
                            <div class="flex items-center space-x-1.5">
                                <span class="text-sm">${{icon}}</span>
                                <span class="text-xs font-bold text-slate-800 truncate">${{task}}</span>
                                ${{isOvr ? '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-1.5 py-0.5 rounded" title="Custom override for this week">Custom</span>' : ''}}
                            </div>
                            <div class="text-sm font-bold text-slate-900 mt-0.5">
                                <a href="c/${{encodeURIComponent(person)}}.html" class="hover:text-blue-600 hover:underline">
                                    ${{person}}
                                </a>
                            </div>
                            <div class="text-[11px] text-slate-500 font-medium">
                                ${{dayDate}} ${{timeInfo}}
                            </div>
                        </div>
                    </div>
                    <a href="c/${{encodeURIComponent(person)}}.html" class="text-slate-400 hover:text-blue-600 p-1.5 rounded-lg hover:bg-blue-50 transition text-xs shrink-0" title="View ${{person}}'s schedule">
                        &rarr;
                    </a>
                `;
                grid.appendChild(card);
            }});

            // Render Trash Duties
            const trashBox = document.getElementById('hub-trash-container');
            trashBox.innerHTML = '';
            const pickups = week.trash_pickups || [];
            if (pickups.length > 0) {{
                pickups.forEach(tp => {{
                    const wasteClass = getWastePillClass(tp.waste_type);
                    const tCard = document.createElement('div');
                    tCard.className = "bg-slate-50 rounded-xl border border-slate-200 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3";
                    tCard.innerHTML = `
                        <div class="flex items-start sm:items-center space-x-3">
                            <span class="text-2xl shrink-0">🗑️</span>
                            <div>
                                <div class="flex items-center flex-wrap gap-1.5">
                                    <span class="text-xs font-bold text-slate-900">${{tp.title || 'Put out the ' + tp.waste_type}}</span>
                                    <span class="px-2 py-0.5 text-[10px] font-bold rounded-md border ${{wasteClass}}">
                                        ${{tp.waste_type}}
                                    </span>
                                </div>
                                <div class="text-xs text-purple-800 font-semibold mt-0.5">
                                    ⏰ Put out bins: <strong>${{tp.reminder_date || tp.date}} at ${{tp.reminder_time || '20:00'}}</strong> (Pickup: ${{tp.pickup_date || tp.date}})
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center space-x-2 shrink-0">
                            <span class="text-xs text-slate-500">Assigned to:</span>
                            <a href="c/${{encodeURIComponent(tp.assigned_to)}}.html" class="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-xs font-bold text-slate-800 hover:border-blue-400 hover:text-blue-600 transition">
                                <span>👤</span>
                                <span>${{tp.assigned_to}}</span>
                            </a>
                        </div>
                    `;
                    trashBox.appendChild(tCard);
                }});
            }} else {{
                trashBox.innerHTML = `
                    <div class="bg-slate-50 rounded-xl border border-dashed border-slate-200 p-3 text-center text-xs text-slate-500">
                        ✅ No special trash bin pickups scheduled for this week.
                    </div>
                `;
            }}

            // Render House Events for This Week
            const houseWrapper = document.getElementById('hub-house-events-wrapper');
            const houseContainer = document.getElementById('hub-house-events-container');
            const weekEvents = (HUB.house_events || []).filter(he => he.date >= week.start_date && he.date <= week.end_date);
            if (weekEvents.length > 0) {{
                houseWrapper.classList.remove('hidden');
                houseContainer.innerHTML = '';
                weekEvents.forEach(he => {{
                    const card = document.createElement('div');
                    card.className = "bg-purple-50/60 border border-purple-200 rounded-xl p-3 text-xs space-y-1";
                    card.innerHTML = `
                        <div class="flex items-center justify-between font-bold text-purple-900">
                            <span>${{he.title}}</span>
                            <span class="font-mono text-[11px] text-purple-600">${{he.date}}</span>
                        </div>
                        ${{he.time ? `<div class="text-[11px] text-slate-600 font-medium">⏰ at ${{he.time}}</div>` : '<div class="text-[11px] text-slate-500">(All day)</div>'}}
                        ${{he.description ? `<p class="text-[11px] text-slate-600 pt-0.5">${{he.description}}</p>` : ''}}
                    `;
                    houseContainer.appendChild(card);
                }});
            }} else {{
                houseWrapper.classList.add('hidden');
            }}

            // Highlight row in full rotation table
            HUB.weeks.forEach((_, rIdx) => {{
                const row = document.getElementById(`hub-rot-row-${{rIdx}}`);
                if (!row) return;
                if (rIdx === idx) {{
                    row.className = "bg-blue-50/90 font-bold border-l-4 border-l-blue-600 text-blue-950 transition cursor-pointer";
                }} else {{
                    row.className = "hover:bg-slate-50/80 transition cursor-pointer";
                }}
            }});
        }}

        function changeHubWeek(delta) {{
            renderHubWeek(currentViewWeekIdx + delta);
        }}

        function onHubWeekSelect(val) {{
            renderHubWeek(parseInt(val, 10));
        }}

        function resetToCurrentWeek() {{
            renderHubWeek(activeCalendarWeekIdx);
        }}

        function toggleHubRotationTable() {{
            const wrapper = document.getElementById('hub-rotation-table-wrapper');
            const arrow = document.getElementById('rotation-toggle-arrow');
            if (!wrapper) return;
            if (wrapper.classList.contains('hidden')) {{
                wrapper.classList.remove('hidden');
                if (arrow) arrow.textContent = '▲ Hide Table';
            }} else {{
                wrapper.classList.add('hidden');
                if (arrow) arrow.textContent = '▼ Show Table';
            }}
        }}

        // Run client-side hydration
        initHub();
    </script>

</body>
</html>""")

    print(f"Static site successfully generated in '{DOCS_DIR}/'")
    return DOCS_DIR

if __name__ == '__main__':
    generate_docs()

