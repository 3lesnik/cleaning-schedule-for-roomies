#!/usr/bin/env python3
"""
Schedule Manager

Handles schedule data persistence (JSON), rotation generation,
trash pickup date mappings (scheduled 1 day prior at 8:00 PM),
customizable weekly task schedules (globally and per person),
house events, and .ics export.
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
DEFAULT_CLEANING_DAY = 5  # 0=Monday, 5=Saturday, 6=Sunday
DEFAULT_CLEANING_TIME = None  # None = All-day event by default

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_SENTINEL = object()

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

    def generate_default_schedule(self, people, tasks, start_date_str, num_weeks, existing_house_events=None, person_preferences=None, default_cleaning_day=DEFAULT_CLEANING_DAY, default_cleaning_time=None):
        """Generate mathematical rotation schedule with trash pickup mappings and customizable task timings."""
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        trash_pickups = self.get_normalized_trash_pickups()
        
        prefs = person_preferences or {}
        weeks = []
        current_date = start_date
        
        for week_idx in range(num_weeks):
            week_start = current_date
            week_end = current_date + datetime.timedelta(days=6)
            week_start_str = week_start.strftime("%Y-%m-%d")
            week_end_str = week_end.strftime("%Y-%m-%d")
            
            assignments = {}
            task_schedules = {}
            trash_person = None
            
            for i, task in enumerate(tasks):
                person = people[(i + week_idx) % len(people)]
                assignments[task] = person
                if "trash" in task.lower():
                    trash_person = person
                
                # Compute scheduled day & time for this task based on person preferences or global default
                if person in prefs and "day_of_week" in prefs[person] and prefs[person]["day_of_week"] is not None:
                    day_of_week = int(prefs[person]["day_of_week"])
                    task_time = prefs[person].get("time")
                else:
                    day_of_week = int(default_cleaning_day)
                    task_time = default_cleaning_time
                
                day_offset = (day_of_week - week_start.weekday()) % 7
                task_date = week_start + datetime.timedelta(days=day_offset)
                task_schedules[task] = {
                    "date": task_date.strftime("%Y-%m-%d"),
                    "day_name": DAY_NAMES[day_of_week],
                    "time": task_time
                }

            # Saturday date for reference
            days_until_saturday = 5 - current_date.weekday()
            if days_until_saturday < 0:
                days_until_saturday += 7
            saturday_date = current_date + datetime.timedelta(days=days_until_saturday)

            # Find trash pickups falling into this week
            # Trash duty is scheduled ONE DAY BEFORE pickup at 8:00 PM
            week_pickups = []
            for tp in trash_pickups:
                if week_start_str <= tp["date"] <= week_end_str:
                    pickup_date = datetime.datetime.strptime(tp["date"], "%Y-%m-%d").date()
                    reminder_date = pickup_date - datetime.timedelta(days=1)
                    week_pickups.append({
                        "date": tp["date"],  # Pickup date
                        "pickup_date": tp["date"],
                        "reminder_date": reminder_date.strftime("%Y-%m-%d"),
                        "reminder_time": "20:00",
                        "waste_type": tp["waste_type"],
                        "title": f"Put out the {tp['waste_type']}",
                        "assigned_to": trash_person
                    })

            weeks.append({
                "week_number": week_idx + 1,
                "start_date": week_start_str,
                "end_date": week_end_str,
                "saturday_date": saturday_date.strftime("%Y-%m-%d"),
                "assignments": assignments,
                "task_schedules": task_schedules,
                "task_overrides": {},
                "trash_pickups": week_pickups
            })
            
            current_date += datetime.timedelta(days=7)
            
        return {
            "people": people,
            "tasks": tasks,
            "start_date": start_date_str,
            "num_weeks": num_weeks,
            "default_cleaning_day": default_cleaning_day,
            "default_cleaning_time": default_cleaning_time,
            "person_preferences": prefs,
            "weeks": weeks,
            "house_events": existing_house_events or []
        }

    def compute_task_schedule(self, week, task, person):
        """Compute the scheduled date and time for a chore in a given week."""
        # 1. Per-week specific override
        overrides = week.get("task_overrides", {})
        if task in overrides:
            return overrides[task]["date"], overrides[task].get("time"), True

        # 2. Per-person preference
        prefs = self.data.get("person_preferences", {})
        week_start = datetime.datetime.strptime(week["start_date"], "%Y-%m-%d").date()

        if person in prefs and "day_of_week" in prefs[person] and prefs[person]["day_of_week"] is not None:
            day_idx = int(prefs[person]["day_of_week"])
            time_val = prefs[person].get("time")
        else:
            day_idx = int(self.data.get("default_cleaning_day", DEFAULT_CLEANING_DAY))
            time_val = self.data.get("default_cleaning_time")

        day_offset = (day_idx - week_start.weekday()) % 7
        task_date = week_start + datetime.timedelta(days=day_offset)
        return task_date.strftime("%Y-%m-%d"), time_val, False

    def refresh_task_schedules(self):
        """Recalculate task_schedules dictionary across all weeks."""
        for week in self.data.get("weeks", []):
            task_schedules = {}
            for task, person in week.get("assignments", {}).items():
                date_str, time_str, is_ovr = self.compute_task_schedule(week, task, person)
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                task_schedules[task] = {
                    "date": date_str,
                    "day_name": DAY_NAMES[d.weekday()],
                    "time": time_str,
                    "is_override": is_ovr
                }
            week["task_schedules"] = task_schedules

    def load_or_initialize(self):
        """Load schedule from JSON file or generate default."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if "weeks" in data and "people" in data and "tasks" in data:
                        data.setdefault("house_events", [])
                        data.setdefault("default_cleaning_day", DEFAULT_CLEANING_DAY)
                        data.setdefault("default_cleaning_time", None)
                        data.setdefault("person_preferences", {})
                        
                        # Ensure all trash pickups have reminder_date, reminder_time, and title
                        for w in data["weeks"]:
                            w.setdefault("task_overrides", {})
                            for tp in w.get("trash_pickups", []):
                                tp.setdefault("pickup_date", tp.get("date"))
                                if "reminder_date" not in tp:
                                    pk = datetime.datetime.strptime(tp["date"], "%Y-%m-%d").date()
                                    tp["reminder_date"] = (pk - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                                tp.setdefault("reminder_time", "20:00")
                                tp.setdefault("title", f"Put out the {tp['waste_type']}")
                                
                        self.data = data
                        self.refresh_task_schedules()
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
        self.refresh_task_schedules()
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

    def adjust_task_schedule(self, week_index, task, date_str, time_str=None):
        """Override the date and time of a specific task occurrence in a specific week."""
        if 0 <= week_index < len(self.data["weeks"]):
            week = self.data["weeks"][week_index]
            week.setdefault("task_overrides", {})
            
            if date_str:
                week["task_overrides"][task] = {
                    "date": date_str,
                    "time": time_str if time_str else None
                }
            else:
                week["task_overrides"].pop(task, None)
                
            self.save_data()
            return True
        return False

    def update_person_preference(self, person, day_of_week, time_str=None):
        """Update a roommate's preferred cleaning day of week and time."""
        self.data.setdefault("person_preferences", {})
        if day_of_week is None or day_of_week == "" or day_of_week == -1:
            self.data["person_preferences"].pop(person, None)
        else:
            self.data["person_preferences"][person] = {
                "day_of_week": int(day_of_week),
                "time": time_str if time_str else None
            }
        self.save_data()
        return self.data["person_preferences"]

    def update_global_schedule_time(self, default_cleaning_day, default_cleaning_time=None):
        """Update the global default cleaning day and time."""
        self.data["default_cleaning_day"] = int(default_cleaning_day)
        self.data["default_cleaning_time"] = default_cleaning_time if default_cleaning_time else None
        self.save_data()
        return {
            "default_cleaning_day": self.data["default_cleaning_day"],
            "default_cleaning_time": self.data["default_cleaning_time"]
        }

    def override_trash_pickup(self, date_str, new_person):
        """Override the assignee of a specific trash pickup date."""
        updated = False
        for week in self.data["weeks"]:
            for tp in week.get("trash_pickups", []):
                if tp["date"] == date_str or tp.get("pickup_date") == date_str:
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
        """Reset current schedule to standard rotation, preserving house events and preferences."""
        self.data = self.generate_default_schedule(
            people=self.data.get("people", DEFAULT_PEOPLE),
            tasks=self.data.get("tasks", DEFAULT_TASKS),
            start_date_str=self.data.get("start_date", DEFAULT_START_DATE),
            num_weeks=self.data.get("num_weeks", DEFAULT_NUM_WEEKS),
            existing_house_events=self.data.get("house_events", []),
            person_preferences=self.data.get("person_preferences", {}),
            default_cleaning_day=self.data.get("default_cleaning_day", DEFAULT_CLEANING_DAY),
            default_cleaning_time=self.data.get("default_cleaning_time")
        )
        self.save_data()
        return self.data

    def update_settings(self, start_date_str=None, num_weeks=None, people=None, tasks=None, default_cleaning_day=None, default_cleaning_time=_SENTINEL, person_preferences=None, start_date=None):
        """Update schedule configuration, number of weeks, and timings, preserving custom week assignments where possible."""
        if start_date_str is None:
            start_date_str = start_date or self.data.get("start_date", DEFAULT_START_DATE)
        if num_weeks is None:
            num_weeks = self.data.get("num_weeks", DEFAULT_NUM_WEEKS)
        num_weeks = int(num_weeks)
        
        current_people = self.data.get("people", DEFAULT_PEOPLE)
        current_tasks = self.data.get("tasks", DEFAULT_TASKS)
        current_start = self.data.get("start_date", DEFAULT_START_DATE)
        current_num_weeks = int(self.data.get("num_weeks", len(self.data.get("weeks", []))))

        if people is None:
            people = current_people
        if tasks is None:
            tasks = current_tasks
        if default_cleaning_day is None:
            default_cleaning_day = self.data.get("default_cleaning_day", DEFAULT_CLEANING_DAY)
        default_cleaning_day = int(default_cleaning_day)
        
        if default_cleaning_time is _SENTINEL:
            default_cleaning_time = self.data.get("default_cleaning_time")
        elif not default_cleaning_time:
            default_cleaning_time = None

        if person_preferences is None:
            person_preferences = self.data.get("person_preferences", {})

        self.data["default_cleaning_day"] = default_cleaning_day
        self.data["default_cleaning_time"] = default_cleaning_time
        self.data["person_preferences"] = person_preferences

        # Did core roster or start date change?
        roster_or_date_changed = (
            people != current_people or
            tasks != current_tasks or
            start_date_str != current_start
        )

        if roster_or_date_changed:
            # Full regeneration required
            self.data = self.generate_default_schedule(
                people=people,
                tasks=tasks,
                start_date_str=start_date_str,
                num_weeks=num_weeks,
                existing_house_events=self.data.get("house_events", []),
                person_preferences=person_preferences,
                default_cleaning_day=default_cleaning_day,
                default_cleaning_time=default_cleaning_time
            )
        else:
            # Roster and start date didn't change. Handle num_weeks extension or reduction
            existing_weeks = self.data.get("weeks", [])
            self.data["num_weeks"] = num_weeks
            
            if len(existing_weeks) < num_weeks:
                # Extend schedule by generating additional weeks
                full_sched = self.generate_default_schedule(
                    people=people,
                    tasks=tasks,
                    start_date_str=start_date_str,
                    num_weeks=num_weeks,
                    existing_house_events=self.data.get("house_events", []),
                    person_preferences=person_preferences,
                    default_cleaning_day=default_cleaning_day,
                    default_cleaning_time=default_cleaning_time
                )
                # Keep existing weeks intact, append newly generated weeks
                new_weeks = existing_weeks + full_sched["weeks"][len(existing_weeks):]
                self.data["weeks"] = new_weeks
            elif len(existing_weeks) > num_weeks:
                # Truncate schedule to num_weeks
                self.data["weeks"] = existing_weeks[:num_weeks]

        # ALWAYS save data to disk and refresh task schedules
        self.save_data()
        return self.data

    def generate_ical_for_person(self, person_name, calendar_name="Apartment Cleaning"):
        """Generate iCalendar bytes for a specific person with exact chore timings, 8:00 PM trash reminders, and house events."""
        cal = Calendar()
        cal.add('prodid', '-//Cleaning Schedule Generator//github.com//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f"{calendar_name} - {person_name}")
        cal.add('x-wr-timezone', 'UTC')
        
        events = []
        
        # 1. Weekly Cleaning Chores (Respecting custom scheduled date and time)
        for week in self.data["weeks"]:
            for task, assigned_person in week["assignments"].items():
                if assigned_person == person_name:
                    date_str, time_str, _ = self.compute_task_schedule(week, task, person_name)
                    task_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    
                    ev = Event()
                    ev.add('summary', task)
                    ev.add('description', f"You are responsible for {task}")
                    
                    if time_str:
                        try:
                            hour, minute = map(int, time_str.split(':'))
                            start_dt = datetime.datetime.combine(task_date, datetime.time(hour, minute))
                            ev.add('dtstart', start_dt)
                            ev.add('dtend', start_dt + datetime.timedelta(hours=1))
                        except Exception:
                            ev.add('dtstart', task_date)
                            ev.add('dtend', task_date + datetime.timedelta(days=1))
                    else:
                        ev.add('dtstart', task_date)
                        ev.add('dtend', task_date + datetime.timedelta(days=1))
                        
                    ev['uid'] = str(uuid.uuid4())
                    ev.add('dtstamp', datetime.datetime.now())
                    events.append(ev)
            
            # 2. Trash Duties: Scheduled ONE DAY BEFORE pickup at 8:00 PM
            for tp in week.get("trash_pickups", []):
                if tp.get("assigned_to") == person_name:
                    waste = tp["waste_type"]
                    title = tp.get("title") or f"Put out the {waste}"
                    
                    # Reminder date is 1 day before pickup date
                    if "reminder_date" in tp:
                        rem_date = datetime.datetime.strptime(tp["reminder_date"], "%Y-%m-%d").date()
                    else:
                        pk_date = datetime.datetime.strptime(tp["date"], "%Y-%m-%d").date()
                        rem_date = pk_date - datetime.timedelta(days=1)
                    
                    # 8:00 PM (20:00) to 8:30 PM (20:30)
                    start_dt = datetime.datetime.combine(rem_date, datetime.time(20, 0))
                    end_dt = datetime.datetime.combine(rem_date, datetime.time(20, 30))
                    
                    tev = Event()
                    tev.add('summary', title)
                    pickup_date_str = tp.get("pickup_date") or tp["date"]
                    tev.add('description', f"Trash pickup is tomorrow ({pickup_date_str}). Put out the {waste} bin tonight by 8:00 pm!")
                    tev.add('dtstart', start_dt)
                    tev.add('dtend', end_dt)
                    tev['uid'] = str(uuid.uuid4())
                    tev.add('dtstamp', datetime.datetime.now())
                    events.append(tev)

        # 3. House Events
        for he in self.data.get("house_events", []):
            if he.get("target_audience") in ["all", person_name]:
                hev = Event()
                hev.add('summary', f"🏠 {he['title']}")
                desc = he.get('description', '') or "Apartment House Event"
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
            f.write(f"{'Week':<6} {'Date':<14} {'Person':<15} {'Task':<45}\n")
            f.write("-" * 80 + "\n")
            
            for week in self.data["weeks"]:
                week_num = week["week_number"]
                week_pickups = week.get("trash_pickups", [])
                pickups_str = ""
                if week_pickups:
                    pickups_str = " [" + ", ".join([f"{tp.get('reminder_date', tp['date'])} 8PM: Put out {tp['waste_type']} ({tp.get('assigned_to')})" for tp in week_pickups]) + "]"

                for task in self.data["tasks"]:
                    person = week["assignments"].get(task, "")
                    sched = week.get("task_schedules", {}).get(task, {})
                    sched_date = sched.get("date", week.get("saturday_date"))
                    time_info = f" {sched.get('time')}" if sched.get('time') else ""
                    date_display = f"{sched_date}{time_info}"
                    
                    display_task = task
                    if "trash" in task.lower() and pickups_str:
                        display_task = f"{task}{pickups_str}"
                    f.write(f"{week_num:<6} {date_display:<14} {person:<15} {display_task:<45}\n")
                f.write("-" * 80 + "\n")
                
            house_events = self.data.get("house_events", [])
            if house_events:
                f.write("\nHOUSE EVENTS\n")
                f.write("=" * 80 + "\n")
                for he in house_events:
                    time_str = f" at {he['time']}" if he.get('time') else " (All day)"
                    audience = f" [For: {he['target_audience']}]" if he.get('target_audience') != 'all' else " [All Roommates]"
                    f.write(f"- {he['date']}{time_str}: {he['title']}{audience}\n")

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
    </style>
</head>
<body>
    <h1>Cleaning Schedule Overview</h1>
    <div class="info">
        <p><strong>Start date:</strong> {start_date.strftime('%A, %B %d, %Y')}</p>
        <p><strong>Number of weeks:</strong> {self.data['num_weeks']}</p>
    </div>
    <table>
        <tr>
            <th>Week</th>
            <th>Scheduled Date</th>
            <th>Person</th>
            <th>Task</th>
        </tr>
""")
            for week in self.data["weeks"]:
                week_pickups = week.get("trash_pickups", [])
                
                for i, task in enumerate(self.data["tasks"]):
                    person = week["assignments"].get(task, "")
                    sched = week.get("task_schedules", {}).get(task, {})
                    sched_date = sched.get("date", week.get("saturday_date"))
                    day_name = sched.get("day_name", "")
                    time_info = f" at {sched.get('time')}" if sched.get('time') else ""
                    date_display = f"{day_name} ({sched_date}){time_info}"
                    
                    task_html = f"<strong>{task}</strong>"
                    if "trash" in task.lower() and week_pickups:
                        badges = "".join([f'<span class="trash-badge">🗑️ Put out {tp["waste_type"]} • {tp.get("reminder_date", tp["date"])} 8:00 PM</span>' for tp in week_pickups])
                        task_html += f"<div style='margin-top:4px;'>{badges}</div>"
                    
                    if i == 0:
                        f.write(f"""        <tr class="week-start">
            <td><strong>Week {week['week_number']}</strong></td>
            <td>{date_display}</td>
            <td><strong>{person}</strong></td>
            <td>{task_html}</td>
        </tr>\n""")
                    else:
                        f.write(f"""        <tr>
            <td></td>
            <td>{date_display}</td>
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
