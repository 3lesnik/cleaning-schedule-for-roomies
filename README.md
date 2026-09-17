# 🧹 Apartment Cleaning, 🗑️ Trash Pickups & 🏠 House Events

A complete solution for managing apartment cleaning schedules, rotating chores, synchronizing trash pickup dates, and organizing communal house events.

Calendar feeds are available as individual **iCalendar (`.ics`) files** and **hosted web pages** that roommates can subscribe to on **iPhone (Apple Calendar)**, **Google Calendar**, or **Android**.

---

## ✨ Features

- **🗑️ Trash Pickup Sync**: Synchronizes all waste pickup dates from `trash_bins.py` (Organic, Residual & Plastic, Paper & Cardboard, Chemical). The person assigned to trash duty for a given week automatically receives all-day events in their calendar for each pickup that week.
- **🏠 House Events**: Schedule shared apartment events (House Meetings, Deep Cleaning Days, Dinners, Rent Due) that automatically sync to everyone's (or targeted) calendars.
- **🌐 Local Interactive Web App**: Modern dashboard to inspect weekly duties, reassign chores, swap tasks between roommates, manage house events, and export calendars.
- **📱 Personal Roommate Pages**: Mobile-friendly landing pages (`/c/<person>`) for each roommate with one-click **"Subscribe in Calendar" (webcal://)**, **"Download .ics"**, and chore schedules.
- **🚀 Free Hosting with GitHub Pages**: Easily export a static site to `docs/` and enable GitHub Pages so all roommates can subscribe to their calendar via public URLs (`https://<username>.github.io/<repo>/calendars/<person>.ics`).

---

## 🚀 Quick Start (Local Web App)

Manage packages and run the application using [`uv`](https://github.com/astral-sh/uv):

```bash
# 1. Install dependencies
uv pip install -e .

# 2. Start the web application
uv run python app.py
```

Open your browser to: **[http://localhost:5001](http://localhost:5001)**

### What you can do in the web app:
- **📅 Weekly Schedule**: View each week's Saturday chores and inline badges for that week's trash pickups. Click any person's name to **reassign** or **swap** chores.
- **👤 Roommate Calendars & Links**: View individual schedules and copy personal calendar links.
- **🗑️ Trash Timeline**: View all 25 trash pickups, filter by waste type, and reassign specific pickup dates.
- **🏠 House Events**: Schedule communal events with titles, dates, times, and descriptions.
- **🚀 Export for GitHub Pages**: One-click generation of the `docs/` folder for static GitHub hosting.

---

## 🌐 Hosting Calendars on GitHub Pages

You can host all calendars for free on GitHub Pages so roommates always have a public subscription link without running a local server:

### Step 1: Export Static Files
In the web dashboard, click **"🚀 Export for GitHub Pages"**, or run:
```bash
uv run python export_static.py
```
This generates the `docs/` directory with:
- `docs/index.html`: Public directory of all roommate calendar links.
- `docs/c/<person>.html`: Personal landing page for each roommate.
- `docs/calendars/<person>.ics`: Static `.ics` feeds ready for calendar apps.
- `docs/.nojekyll`: Enables raw file serving on GitHub Pages.

### Step 2: Push to GitHub
```bash
git add .
git commit -m "Initialize cleaning & trash calendar schedule with GitHub Pages"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
git push -u origin main
```

### Step 3: Enable GitHub Pages
1. Go to your repository on GitHub &rarr; **Settings** &rarr; **Pages**.
2. Under **Build and deployment** &gt; **Branch**:
   - Select branch: `main`
   - Select folder: `/docs`
   - Click **Save**.
3. Within 1-2 minutes, your site will be live at:
   - **Hub**: `https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/`
   - **Personal Page**: `https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/c/Nancy.html`
   - **Direct Calendar Feed**: `https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/calendars/Nancy.ics`

---

## 📲 How Roommates Subscribe to Their Calendar

### 🍏 iPhone / iPad / Mac (Apple Calendar)
1. Open your personal page (`/c/<person>`) on your device.
2. Tap **"📲 Subscribe in Calendar"**.
3. iOS will prompt: *"Subscribe to the calendar?"* &rarr; Tap **Subscribe**.
4. Set Auto-refresh to **Every day** or **Every hour**.

### 📅 Google Calendar (Android & Web)
1. On your personal page, click **"📋 Copy Feed URL"**.
2. Open [Google Calendar on the web](https://calendar.google.com).
3. On the left sidebar, next to **Other calendars**, click the **+** icon &rarr; **From URL**.
4. Paste the feed URL and click **Add calendar**.
5. The calendar will sync to Google Calendar and your Android device.

---

## 💻 CLI Usage

You can also generate files directly via the command line:

```bash
# Generate cleaning schedule and update the schedules/ directory
uv run python create_your_schedule.py

# Run test suite
uv run python -m unittest test_schedule.py
```

---

## 📁 Project Structure

```
calendarrs/
├── app.py                   # Flask web server (dynamic dashboard & calendar feeds)
├── export_static.py         # Static site generator for GitHub Pages (docs/)
├── schedule_manager.py      # Core state manager, house events, and .ics generation
├── cleaning_schedule.py     # iCalendar rotation logic
├── generate_overview.py     # Text & HTML schedule overview generator
├── create_your_schedule.py  # CLI schedule generator
├── trash_bins.py            # Trash pickup dates & waste types
├── schedule_data.json       # JSON persistence store for schedule & house events
├── templates/
│   ├── index.html           # Main interactive web dashboard
│   └── roommate.html        # Shareable personal calendar landing page
├── docs/                    # Static site for GitHub Pages hosting
│   ├── index.html           # Public directory
│   ├── c/                   # Roommate personal landing pages
│   └── calendars/           # Static .ics calendar files
├── schedules/               # Local copy of exported .ics and overview files
├── test_schedule.py         # Automated unit test suite
├── pyproject.toml           # Project dependencies managed with uv
└── .gitignore               # Git ignore rules
```

---

## 👥 Roommates

- Nancy
- Natan
- Shlomo
- Lucia
- Tom / Brenda
- Ellie
