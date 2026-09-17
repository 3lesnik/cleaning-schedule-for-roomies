#!/usr/bin/env python3
"""
Schedule Manager

Handles schedule data persistence (JSON), initial rotation generation,
trash pickup date mappings, reassignments, swapping, house events, and .ics export.
"""

import os
import json
import datetime
import uuid
import zipfile
import io
from icalendar import Calendar, Event
import trash_bins

DATA_FILE = "schedule_data.json"
SCHEDULES_DIR = "schedules"

DEFAULT_PEOPLE = ["Nancy", "Natan", "Shlomo", "Lucia", "Tom", "Ellie"]
DEFAULT_TASKS = [
    "Kitchen",
    "Bathroom",
    "Downstairs Toilet",
    "Floors duty",
    "Taking out trash",
    "Communal laundry"
]
DEFAULT_START_DATE = "2026-08-31"  # Monday
DEFAULT_NUM_WEEKS = 18

class ScheduleManager:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.data = self.load_or_initialize()

    def get_normalized_trash_pickups(self):
        """Return trash pickups from trash_bins with datetime.date and string formats."""
        pickups = []
        for item in trash_bins.schedule:
            d = item['date']
            if isinstance(d, str):
                dt = datetime.datetime.strptime(d, "%Y-%m-%d").date()
            else:
                dt = d
            pickups.append({
                "date": dt.strftime("%Y-%m-%d"),
                "waste_type": item["waste_type"]
            })
        pickups.sort(key=lambda x: x["date"])
        return pickups

    def generate_default_schedule(self, people, tasks, start_date_str, num_weeks, existing_house_events=None):
        """Generate mathematical rotation schedule with trash pickup mappings."""
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        trash_pickups = self.get_normalized_trash_pickups()
        
        weeks = []
        current_date = start_date
        
        for week_idx in range(num_weeks):
            week_start = current_date
            week_end = current_date + datetime.timedelta(days=6)
            
            # Saturday of this week
            days_until_saturday = 5 - current_date.weekday()
            if days_until_saturday < 0:
                days_until_saturday += 7
            saturday_date = current_date + datetime.timedelta(days=days_until_saturday)
            
            assignments = {}
            trash_person = None
            for i, task in enumerate(tasks):
                person = people[(i + week_idx) % len(people)]
                assignments[task] = person
                if "trash" in task.lower():
                    trash_person = person

            # Find trash pickups falling into this week
            week_start_str = week_start.strftime("%Y-%m-%d")
            week_end_str = week_end.strftime("%Y-%m-%d")
            
            week_pickups = []
            for tp in trash_pickups:
                if week_start_str <= tp["date"] <= week_end_str:
                    week_pickups.append({
                        "date": tp["date"],
                        "waste_type": tp["waste_type"],
                        "assigned_to": trash_person
                    })

            weeks.append({
                "week_number": week_idx + 1,
                "start_date": week_start_str,
                "end_date": week_end_str,
                "saturday_date": saturday_date.strftime("%Y-%m-%d"),
                "assignments": assignments,
                "trash_pickups": week_pickups
            })
            
            current_date += datetime.timedelta(days=7)
            
        return {
            "people": people,
            "tasks": tasks,
            "start_date": start_date_str,
            "num_weeks": num_weeks,
            "weeks": weeks,
            "house_events": existing_house_events or []
        }

    def load_or_initialize(self):
        """Load schedule from JSON file or generate default."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if "weeks" in data and "people" in data and "tasks" in data:
                        data.setdefault("house_events", [])
                        return data
            except Exception as e:
                print(f"Error loading {self.data_file}: {e}, generating defaults...")
        
        data = self.generate_default_schedule(
            people=DEFAULT_PEOPLE,
            tasks=DEFAULT_TASKS,
            start_date_str=DEFAULT_START_DATE,
            num_weeks=DEFAULT_NUM_WEEKS
        )
        self.save_data(data)
        return data

    def save_data(self, data=None):
        """Save schedule data to JSON file."""
        if data is not None:
            self.data = data
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def reassign_task(self, week_index, task, new_person):
        """Reassign a task in a specific week to a new person."""
        if 0 <= week_index < len(self.data["weeks"]):
            week = self.data["weeks"][week_index]
            week["assignments"][task] = new_person
            
            # If this is the trash task, update assigned_to for this week's trash pickups
            if "trash" in task.lower():
                for tp in week.get("trash_pickups", []):
                    tp["assigned_to"] = new_person
            
            self.save_data()
            return True
        return False

    def swap_tasks(self, week_index, person1, person2):
        """Swap assigned tasks between two people in a specific week."""
        if 0 <= week_index < len(self.data["weeks"]):
            week = self.data["weeks"][week_index]
            assignments = week["assignments"]
            
            task1 = None
            task2 = None
            for t, p in assignments.items():
                if p == person1 and task1 is None:
                    task1 = t
                elif p == person2 and task2 is None:
                    task2 = t
            
            if task1 and task2:
                assignments[task1] = person2
                assignments[task2] = person1
                
                # Check trash pickups update
                for tp in week.get("trash_pickups", []):
                    if "trash" in task1.lower():
                        tp["assigned_to"] = person2
                    elif "trash" in task2.lower():
                        tp["assigned_to"] = person1
                        
                self.save_data()
                return True
        return False

    def override_trash_pickup(self, date_str, new_person):
        """Override the assignee of a specific trash pickup date."""
        updated = False
        for week in self.data["weeks"]:
            for tp in week.get("trash_pickups", []):
                if tp["date"] == date_str:
                    tp["assigned_to"] = new_person
                    updated = True
        if updated:
            self.save_data()
        return updated

    # --- House Events ---
    def add_house_event(self, title, date_str, time_str=None, description="", target_audience="all"):
        """Add a house event that will sync to targeted roommates' calendars."""
        event_id = str(uuid.uuid4())[:8]
        event = {
            "id": event_id,
            "title": title.strip(),
            "date": date_str.strip(),
            "time": time_str.strip() if time_str else None,
            "description": description.strip(),
            "target_audience": target_audience.strip() if target_audience else "all"
        }
        self.data.setdefault("house_events", [])
        self.data["house_events"].append(event)
        self.data["house_events"].sort(key=lambda x: (x["date"], x.get("time") or "00:00"))
        self.save_data()
        return event

    def delete_house_event(self, event_id):
        """Delete a house event by ID."""
        if "house_events" not in self.data:
            return False
        before_count = len(self.data["house_events"])
        self.data["house_events"] = [e for e in self.data["house_events"] if e.get("id") != event_id]
        if len(self.data["house_events"]) < before_count:
            self.save_data()
            return True
        return False

    def get_house_events(self):
        """Return all house events."""
        return self.data.get("house_events", [])

    def reset_to_rotation(self):
        """Reset current schedule to standard rotation, preserving house events."""
        self.data = self.generate_default_schedule(
            people=self.data.get("people", DEFAULT_PEOPLE),
            tasks=self.data.get("tasks", DEFAULT_TASKS),
            start_date_str=self.data.get("start_date", DEFAULT_START_DATE),
            num_weeks=self.data.get("num_weeks", DEFAULT_NUM_WEEKS),
            existing_house_events=self.data.get("house_events", [])
        )
        self.save_data()
        return self.data

    def update_settings(self, start_date_str, num_weeks, people=None, tasks=None):
        """Update schedule configuration and regenerate."""
        if people is None:
            people = self.data.get("people", DEFAULT_PEOPLE)
        if tasks is None:
            tasks = self.data.get("tasks", DEFAULT_TASKS)
            
        self.data = self.generate_default_schedule(
            people=people,
            tasks=tasks,
            start_date_str=start_date_str,
            num_weeks=num_weeks,
            existing_house_events=self.data.get("house_events", [])
        )
        self.save_data()
        return self.data

    def generate_ical_for_person(self, person_name, calendar_name="Apartment Cleaning"):
        """Generate iCalendar bytes for a specific person including cleaning, trash, and house events."""
        cal = Calendar()
        cal.add('prodid', '-//Cleaning Schedule Generator//github.com//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f"{calendar_name} - {person_name}")
        cal.add('x-wr-timezone', 'UTC')
        
        events = []
        
        # 1. Saturday Cleaning Chores
        for week in self.data["weeks"]:
            saturday_date = datetime.datetime.strptime(week["saturday_date"], "%Y-%m-%d").date()
            
            for task, assigned_person in week["assignments"].items():
                if assigned_person == person_name:
                    ev = Event()
                    ev.add('summary', task)
                    ev.add('description', f"You are responsible for {task} this Saturday")
                    ev.add('dtstart', saturday_date)
                    ev.add('dtend', saturday_date + datetime.timedelta(days=1))
                    ev['uid'] = str(uuid.uuid4())
                    ev.add('dtstamp', datetime.datetime.now())
                    events.append(ev)
            
            # 2. Trash Pickups
            for tp in week.get("trash_pickups", []):
                if tp.get("assigned_to") == person_name:
                    pdate = datetime.datetime.strptime(tp["date"], "%Y-%m-%d").date()
                    waste = tp["waste_type"]
                    tev = Event()
                    tev.add('summary', f"Trash: {waste}")
                    tev.add('description', f"Trash pickup for {waste}. You are responsible for taking out the trash this week!")
                    tev.add('dtstart', pdate)
                    tev.add('dtend', pdate + datetime.timedelta(days=1))
                    tev['uid'] = str(uuid.uuid4())
                    tev.add('dtstamp', datetime.datetime.now())
                    events.append(tev)

        # 3. House Events
        for he in self.data.get("house_events", []):
            if he.get("target_audience") in ["all", person_name]:
                hev = Event()
                hev.add('summary', f"🏠 {he['title']}")
                desc = he.get('description', '')
                if not desc:
                    desc = "Apartment House Event"
                hev.add('description', desc)
                
                date_val = datetime.datetime.strptime(he['date'], "%Y-%m-%d").date()
                time_val = he.get('time')
                if time_val:
                    try:
                        hour, minute = map(int, time_val.split(':'))
                        start_dt = datetime.datetime.combine(date_val, datetime.time(hour, minute))
                        hev.add('dtstart', start_dt)
                        hev.add('dtend', start_dt + datetime.timedelta(hours=1))
                    except Exception:
                        hev.add('dtstart', date_val)
                        hev.add('dtend', date_val + datetime.timedelta(days=1))
                else:
                    hev.add('dtstart', date_val)
                    hev.add('dtend', date_val + datetime.timedelta(days=1))
                    
                hev['uid'] = f"house-{he.get('id', uuid.uuid4())}@calendarrs"
                hev.add('dtstamp', datetime.datetime.now())
                events.append(hev)
        
        # Chronological sort supporting both date and datetime
        def get_sort_key(ev):
            dt_prop = ev.get('dtstart')
            if not dt_prop:
                return datetime.datetime.min
            val = dt_prop.dt
            if isinstance(val, datetime.datetime):
                return val
            return datetime.datetime.combine(val, datetime.time.min)
            
        events.sort(key=get_sort_key)
        
        for ev in events:
            cal.add_component(ev)
            
        return cal.to_ical()

    def sync_to_filesystem(self, output_dir=SCHEDULES_DIR):
        """Write all .ics files, text overview, and HTML overview to output_dir."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        generated_files = []
        
        # Generate .ics for each person
        for person in self.data["people"]:
            ical_bytes = self.generate_ical_for_person(person)
            filename = os.path.join(output_dir, f"cleaning_schedule_{person.replace(' ', '_')}.ics")
            with open(filename, 'wb') as f:
                f.write(ical_bytes)
            generated_files.append(filename)
            
        # Generate text overview
        txt_path = os.path.join(output_dir, "cleaning_schedule_overview.txt")
        start_date = datetime.datetime.strptime(self.data["start_date"], "%Y-%m-%d").date()
        with open(txt_path, 'w') as f:
            f.write("CLEANING SCHEDULE OVERVIEW\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Start date: {start_date.strftime('%A, %B %d, %Y')}\n")
            f.write(f"Number of weeks: {self.data['num_weeks']}\n\n")
            f.write(f"{'Week':<6} {'Date':<12} {'Person':<15} {'Task':<45}\n")
            f.write("-" * 80 + "\n")
            
            for week in self.data["weeks"]:
                week_num = week["week_number"]
                sat_str = week["saturday_date"]
                week_pickups = week.get("trash_pickups", [])
                pickups_str = ""
                if week_pickups:
                    pickups_str = " [" + ", ".join([f"{tp['date']}: {tp['waste_type']} ({tp.get('assigned_to')})" for tp in week_pickups]) + "]"

                for task in self.data["tasks"]:
                    person = week["assignments"].get(task, "")
                    display_task = task
                    if "trash" in task.lower() and pickups_str:
                        display_task = f"{task}{pickups_str}"
                    f.write(f"{week_num:<6} {sat_str:<12} {person:<15} {display_task:<45}\n")
                f.write("-" * 80 + "\n")
                
            # List house events if any
            house_events = self.data.get("house_events", [])
            if house_events:
                f.write("\nHOUSE EVENTS\n")
                f.write("=" * 80 + "\n")
                for he in house_events:
                    time_str = f" at {he['time']}" if he.get('time') else " (All day)"
                    audience = f" [For: {he['target_audience']}]" if he.get('target_audience') != 'all' else " [All Roommates]"
                    f.write(f"- {he['date']}{time_str}: {he['title']}{audience}\n")
                    if he.get('description'):
                        f.write(f"  Note: {he['description']}\n")

        generated_files.append(txt_path)
        
        # Generate HTML overview
        html_path = os.path.join(output_dir, "cleaning_schedule_overview.html")
        with open(html_path, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Cleaning Schedule Overview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 30px auto;
            max-width: 1000px;
            padding: 0 20px;
            color: #333;
            line-height: 1.6;
        }}
        h1 {{
            color: #1e293b;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
        }}
        .info {{
            margin-bottom: 20px;
            background: #f8fafc;
            padding: 15px 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #3b82f6;
            color: white;
            text-align: left;
            padding: 12px;
            font-size: 14px;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }}
        tr.week-start {{
            border-top: 2px solid #64748b;
        }}
        tr:hover {{
            background-color: #f1f5f9;
        }}
        .trash-badge {{
            display: inline-block;
            background: #e0f2fe;
            color: #0369a1;
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 9999px;
            margin: 2px 4px 2px 0;
            font-weight: 500;
        }}
        .event-card {{
            background: #fdf4ff;
            border: 1px solid #f0abfc;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <h1>Cleaning Schedule Overview</h1>
    <div class="info">
        <p><strong>Start date:</strong> {start_date.strftime('%A, %B %d, %Y')}</p>
        <p><strong>Number of weeks:</strong> {self.data['num_weeks']}</p>
    </div>
""")
            house_events = self.data.get("house_events", [])
            if house_events:
                f.write("""    <div class="info" style="background:#faf5ff; border-color:#e9d5ff;">
        <h2 style="margin-top:0; color:#7e22ce; font-size:16px;">🏠 Upcoming House Events</h2>\n""")
                for he in house_events:
                    time_info = f" at {he['time']}" if he.get('time') else " (All day)"
                    f.write(f"""        <div class="event-card">
            <strong>{he['title']}</strong> — {he['date']}{time_info}
            <div style="font-size:12px; color:#6b7280; margin-top:2px;">{he.get('description', '')}</div>
        </div>\n""")
                f.write("    </div>\n")

            f.write("""    <table>
        <tr>
            <th>Week</th>
            <th>Saturday Cleaning</th>
            <th>Person</th>
            <th>Task</th>
        </tr>
""")
            for week in self.data["weeks"]:
                sat_date = datetime.datetime.strptime(week["saturday_date"], "%Y-%m-%d").strftime("%B %d, %Y")
                week_pickups = week.get("trash_pickups", [])
                
                for i, task in enumerate(self.data["tasks"]):
                    person = week["assignments"].get(task, "")
                    task_html = f"<strong>{task}</strong>"
                    if "trash" in task.lower() and week_pickups:
                        badges = "".join([f'<span class="trash-badge">🗑️ {tp["date"]}: {tp["waste_type"]}</span>' for tp in week_pickups])
                        task_html += f"<div style='margin-top:4px;'>{badges}</div>"
                    
                    if i == 0:
                        f.write(f"""        <tr class="week-start">
            <td><strong>Week {week['week_number']}</strong></td>
            <td>{sat_date}</td>
            <td><strong>{person}</strong></td>
            <td>{task_html}</td>
        </tr>\n""")
                    else:
                        f.write(f"""        <tr>
            <td></td>
            <td></td>
            <td><strong>{person}</strong></td>
            <td>{task_html}</td>
        </tr>\n""")
            f.write("""    </table>
</body>
</html>""")
        generated_files.append(html_path)
        return generated_files

    def export_all_zip(self):
        """Create an in-memory zip file containing all .ics and overview files."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for person in self.data["people"]:
                ical_bytes = self.generate_ical_for_person(person)
                zf.writestr(f"cleaning_schedule_{person.replace(' ', '_')}.ics", ical_bytes)
            
            # Add overview text and HTML
            self.sync_to_filesystem()
            txt_path = os.path.join(SCHEDULES_DIR, "cleaning_schedule_overview.txt")
            if os.path.exists(txt_path):
                with open(txt_path, 'r') as f:
                    zf.writestr("cleaning_schedule_overview.txt", f.read())
            html_path = os.path.join(SCHEDULES_DIR, "cleaning_schedule_overview.html")
            if os.path.exists(html_path):
                with open(html_path, 'r') as f:
                    zf.writestr("cleaning_schedule_overview.html", f.read())
                    
        buf.seek(0)
        return buf.getvalue()
