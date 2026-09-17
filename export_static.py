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
from schedule_manager import ScheduleManager

DOCS_DIR = "docs"

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
                    <a id="webcal-btn" href="#" class="inline-flex items-center space-x-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition">
                        <span>📲</span>
                        <span>Subscribe in Calendar (Apple/iOS/Mac)</span>
                    </a>
                    <a href="../calendars/{person}.ics" download="cleaning_schedule_{person}.ics" class="inline-flex items-center space-x-2 px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl border border-slate-300 shadow-xs transition">
                        <span>📥</span>
                        <span>Download .ics File</span>
                    </a>
                    <button onclick="copyFeedUrl()" class="inline-flex items-center space-x-2 px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl border border-slate-300 shadow-xs transition">
                        <span>🔗</span>
                        <span>Copy Feed URL</span>
                    </button>
                </div>
                <div class="text-[11px] text-slate-500 pt-1">
                    <strong>For Google Calendar:</strong> Copy the feed URL &rarr; Go to <a href="https://calendar.google.com/calendar/r/settings/addbyurl" target="_blank" class="text-blue-600 underline">Google Calendar &gt; Add Calendar &gt; From URL</a> &rarr; Paste link.
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

    <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <span class="text-3xl">🧹</span>
                <div>
                    <h1 class="text-xl font-bold text-slate-900 leading-tight">Apartment Cleaning & Trash Hub</h1>
                    <p class="text-xs text-slate-500">Live calendar subscriptions & hosted pages for all roommates</p>
                </div>
            </div>
            <a href="calendars/cleaning_schedules.zip" id="zip-dl-link" class="hidden sm:inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition">
                <span>📥</span>
                <span>Download All (.zip)</span>
            </a>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8 flex-1 w-full space-y-8">
        
        <!-- Roommate Cards Directory -->
        <div>
            <h2 class="text-lg font-bold text-slate-900 mb-1">Roommate Calendars & Personal Links</h2>
            <p class="text-xs text-slate-500 mb-4">Click your name to view your schedule or subscribe to your personal live calendar.</p>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
""")
        for person in people:
            f.write(f"""                <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:shadow-md transition space-y-4">
                    <div class="flex items-center space-x-3">
                        <div class="w-12 h-12 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center text-xl font-bold shadow-xs">
                            {person[0]}
                        </div>
                        <div>
                            <h3 class="text-base font-bold text-slate-900">{person}</h3>
                            <a href="c/{person}.html" class="text-xs text-blue-600 hover:text-blue-800 font-medium">Open Personal Page &rarr;</a>
                        </div>
                    </div>

                    <div class="flex items-center space-x-2 pt-2 border-t border-slate-100">
                        <a href="c/{person}.html" class="flex-1 text-center py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition">
                            View Schedule
                        </a>
                        <a href="calendars/{person}.ics" download="cleaning_schedule_{person}.ics" class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition" title="Download .ics">
                            📥 .ics
                        </a>
                    </div>
                </div>\n""")

        f.write(f"""            </div>
        </div>

        <!-- House Events Banner (if any) -->
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

        f.write(f"""        <!-- How to Subscribe Guide -->
        <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <h2 class="text-base font-bold text-slate-900">How to Subscribe to Your Calendar</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600">
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <h3 class="font-bold text-slate-900">📱 iPhone / Apple Calendar</h3>
                    <p>Open your personal page on your iPhone and tap <strong>"Subscribe in Calendar"</strong>. iOS will automatically prompt to add the calendar feed.</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <h3 class="font-bold text-slate-900">📅 Google Calendar</h3>
                    <p>Click <strong>"Copy Feed URL"</strong> on your page. Open Google Calendar &gt; Other calendars (+) &gt; <strong>From URL</strong> &gt; Paste the link.</p>
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

</body>
</html>""")

    print(f"Static site successfully generated in '{DOCS_DIR}/'")
    return DOCS_DIR

if __name__ == '__main__':
    generate_docs()
