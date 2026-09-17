#!/usr/bin/env python3
"""
Comprehensive Test Suite for Cleaning Schedule, Trash Pickups, House Events, and Hosting
"""

import unittest
import unittest.mock
from unittest.mock import patch, MagicMock
import json
import os
import io
import datetime
import zipfile
from icalendar import Calendar
from schedule_manager import ScheduleManager
from app import app
import export_static

class TestCleaningSchedule(unittest.TestCase):
    def setUp(self):
        self.test_data_file = "test_schedule_data.json"
        if os.path.exists(self.test_data_file):
            os.remove(self.test_data_file)
        self.manager = ScheduleManager(data_file=self.test_data_file)
        self.client = app.test_client()

    def tearDown(self):
        if os.path.exists(self.test_data_file):
            os.remove(self.test_data_file)

    def test_people_names(self):
        """Verify Nicole is replaced with Nancy and Gauresh is replaced with Natan."""
        people = self.manager.data["people"]
        self.assertIn("Nancy", people)
        self.assertIn("Natan", people)
        self.assertNotIn("Nicole", people)
        self.assertNotIn("Guaresh", people)

    def test_trash_pickups_mapping(self):
        """Verify trash pickups are mapped to people on trash duty."""
        all_assigned_pickups = []
        for week in self.manager.data["weeks"]:
            for tp in week.get("trash_pickups", []):
                all_assigned_pickups.append(tp)
                trash_person = None
                for task, person in week["assignments"].items():
                    if "trash" in task.lower():
                        trash_person = person
                self.assertEqual(tp["assigned_to"], trash_person)
        
        self.assertEqual(len(all_assigned_pickups), 25)

    def test_house_events(self):
        """Verify adding and deleting house events."""
        event = self.manager.add_house_event(
            title="Apartment Dinner",
            date_str="2026-10-15",
            time_str="19:30",
            description="Taco night in the communal kitchen",
            target_audience="all"
        )
        self.assertIsNotNone(event["id"])
        self.assertEqual(event["title"], "Apartment Dinner")
        self.assertEqual(len(self.manager.get_house_events()), 1)

        # Verify event appears in Nancy's calendar
        ical_bytes = self.manager.generate_ical_for_person("Nancy")
        cal = Calendar.from_ical(ical_bytes)
        summaries = [str(ev.get("summary")) for ev in cal.walk('VEVENT')]
        self.assertTrue(any("Apartment Dinner" in s for s in summaries))

        # Delete event
        deleted = self.manager.delete_house_event(event["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(self.manager.get_house_events()), 0)

    def test_reassign_and_swap(self):
        """Verify reassigning and swapping tasks."""
        week_0 = self.manager.data["weeks"][0]
        person1 = week_0["assignments"]["Kitchen"]
        person2 = week_0["assignments"]["Bathroom"]
        self.manager.swap_tasks(0, person1, person2)
        self.assertEqual(self.manager.data["weeks"][0]["assignments"]["Kitchen"], person2)

    def test_shareable_roommate_page(self):
        """Verify GET /c/<person> renders roommate page."""
        first_person = self.manager.data["people"][0]
        res = self.client.get(f'/c/{first_person}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(first_person.encode(), res.data)
        self.assertIn(b"Subscribe in Calendar", res.data)

    def test_direct_calendar_feed(self):
        """Verify GET /calendars/<person>.ics returns live iCalendar feed."""
        first_person = self.manager.data["people"][0]
        res = self.client.get(f'/calendars/{first_person}.ics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"BEGIN:VCALENDAR", res.data)
        self.assertIn("text/calendar", res.headers.get("Content-Type", ""))

    def test_trash_pickup_reminders(self):
        """Verify trash duties are scheduled 1 day before pickup at 20:00 titled 'Put out the {type of trash}'."""
        for week in self.manager.data["weeks"]:
            for tp in week.get("trash_pickups", []):
                self.assertEqual(tp["reminder_time"], "20:00")
                self.assertEqual(tp["title"], f"Put out the {tp['waste_type']}")
                pk_date = datetime.datetime.strptime(tp["pickup_date"], "%Y-%m-%d").date()
                rm_date = datetime.datetime.strptime(tp["reminder_date"], "%Y-%m-%d").date()
                self.assertEqual(rm_date, pk_date - datetime.timedelta(days=1))
                
        # Check that icalendar events reflect 20:00-20:30 and 'Put out the {waste}' title
        first_trash_person = None
        first_tp = None
        for week in self.manager.data["weeks"]:
            if week.get("trash_pickups"):
                first_tp = week["trash_pickups"][0]
                first_trash_person = first_tp["assigned_to"]
                break
        self.assertIsNotNone(first_trash_person)
        
        ical_bytes = self.manager.generate_ical_for_person(first_trash_person)
        cal = Calendar.from_ical(ical_bytes)
        trash_events = [ev for ev in cal.walk('VEVENT') if str(ev.get('summary', '')).startswith("Put out the ")]
        self.assertGreater(len(trash_events), 0)
        
        matching = [ev for ev in trash_events if str(ev.get('summary')) == first_tp["title"]]
        self.assertGreater(len(matching), 0)
        ev = matching[0]
        dtstart = ev.get('dtstart').dt
        dtend = ev.get('dtend').dt
        self.assertIsInstance(dtstart, datetime.datetime)
        self.assertEqual(dtstart.hour, 20)
        self.assertEqual(dtstart.minute, 0)
        self.assertEqual(dtend.hour, 20)
        self.assertEqual(dtend.minute, 30)

    def test_global_cleaning_day_and_time(self):
        """Verify updating global cleaning day and time."""
        self.manager.update_global_schedule_time(default_cleaning_day=6, default_cleaning_time="14:00")
        self.assertEqual(self.manager.data["default_cleaning_day"], 6)
        self.assertEqual(self.manager.data["default_cleaning_time"], "14:00")
        
        # Test schedule computation for a person with no override
        week_0 = self.manager.data["weeks"][0]
        person = week_0["assignments"]["Kitchen"]
        date_str, time_str, is_ovr = self.manager.compute_task_schedule(week_0, "Kitchen", person)
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 6)  # Sunday
        self.assertEqual(time_str, "14:00")
        self.assertFalse(is_ovr)

    def test_roommate_preferences(self):
        """Verify per-roommate cleaning day and time preferences."""
        # Set Nancy to Friday (4) at 10:30
        self.manager.update_person_preference("Nancy", day_of_week=4, time_str="10:30")
        self.assertIn("Nancy", self.manager.data["person_preferences"])
        self.assertEqual(self.manager.data["person_preferences"]["Nancy"]["day_of_week"], 4)
        self.assertEqual(self.manager.data["person_preferences"]["Nancy"]["time"], "10:30")

        # Find Nancy's task in week 0
        week_0 = self.manager.data["weeks"][0]
        nancy_task = None
        other_task = None
        other_person = None
        for task, person in week_0["assignments"].items():
            if person == "Nancy":
                nancy_task = task
            elif other_person is None:
                other_task = task
                other_person = person

        date_str, time_str, _ = self.manager.compute_task_schedule(week_0, nancy_task, "Nancy")
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 4)  # Friday
        self.assertEqual(time_str, "10:30")

        # Other roommate should follow default cleaning day (Saturday = 5)
        o_date_str, _, _ = self.manager.compute_task_schedule(week_0, other_task, other_person)
        o_d = datetime.datetime.strptime(o_date_str, "%Y-%m-%d").date()
        self.assertEqual(o_d.weekday(), 5)

        # Clear Nancy's preference
        self.manager.update_person_preference("Nancy", day_of_week=None)
        self.assertNotIn("Nancy", self.manager.data["person_preferences"])

    def test_task_overrides(self):
        """Verify task occurrence reschedule overrides."""
        self.manager.adjust_task_schedule(0, "Kitchen", "2026-10-10", "16:45")
        week_0 = self.manager.data["weeks"][0]
        person = week_0["assignments"]["Kitchen"]
        date_str, time_str, is_ovr = self.manager.compute_task_schedule(week_0, "Kitchen", person)
        self.assertEqual(date_str, "2026-10-10")
        self.assertEqual(time_str, "16:45")
        self.assertTrue(is_ovr)

        # Clear override
        self.manager.adjust_task_schedule(0, "Kitchen", None)
        date_str2, time_str2, is_ovr2 = self.manager.compute_task_schedule(week_0, "Kitchen", person)
        self.assertFalse(is_ovr2)

    def test_api_preferences_and_task_schedule(self):
        """Verify API endpoints for roommate preferences and task rescheduling."""
        # 1. Update preference via API
        res = self.client.post('/api/preferences', json={
            "person": "Natan",
            "day_of_week": 3,
            "time": "18:00"
        })
        self.assertEqual(res.status_code, 200)
        res_json = json.loads(res.data)
        self.assertEqual(res_json["status"], "ok")
        self.assertEqual(res_json["preferences"]["Natan"]["day_of_week"], 3)
        self.assertEqual(res_json["preferences"]["Natan"]["time"], "18:00")

        # 2. Reschedule task via API
        res2 = self.client.post('/api/task_schedule', json={
            "week_index": 0,
            "task": "Bathroom",
            "date": "2026-09-28",
            "time": "11:00"
        })
        self.assertEqual(res2.status_code, 200)
        res2_json = json.loads(res2.data)
        self.assertEqual(res2_json["status"], "ok")

        # 3. Update global settings via API
        res3 = self.client.post('/api/settings', json={
            "start_date": "2026-09-07",
            "num_weeks": 26,
            "people": ["Nancy", "Natan", "Ellie", "Lucia", "Shlomo"],
            "tasks": ["Kitchen", "Bathroom", "Hallway & Stairs", "Trash & Recycling", "Living Room"],
            "default_cleaning_day": 6,
            "default_cleaning_time": "14:30",
            "person_preferences": {}
        })
        self.assertEqual(res3.status_code, 200)
        res3_json = json.loads(res3.data)
        self.assertEqual(res3_json["status"], "ok")
        self.assertEqual(res3_json["data"]["default_cleaning_day"], 6)
        self.assertEqual(res3_json["data"]["default_cleaning_time"], "14:30")

    def test_static_site_generation(self):
        """Verify export_static creates docs/ structure."""
        docs_dir = export_static.generate_docs(self.manager)
        self.assertTrue(os.path.exists(os.path.join(docs_dir, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(docs_dir, ".nojekyll")))
        for person in self.manager.data["people"]:
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "calendars", f"{person}.ics")))
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "c", f"{person}.html")))

    @unittest.mock.patch('subprocess.run')
    def test_publish_endpoint(self, mock_run):
        """Verify POST /api/publish regenerates docs, commits, and pushes to git."""
        mock_proc = unittest.mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        res = self.client.post('/api/publish', json={"message": "Test auto-publish"})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertIn("Successfully exported and pushed", data["message"])

if __name__ == '__main__':
    unittest.main()
