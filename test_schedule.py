#!/usr/bin/env python3
"""
Comprehensive Test Suite for Cleaning Schedule, Trash Pickups, House Events, and Hosting
"""

import unittest
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

    def test_static_site_generation(self):
        """Verify export_static creates docs/ structure."""
        docs_dir = export_static.generate_docs(self.manager)
        self.assertTrue(os.path.exists(os.path.join(docs_dir, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(docs_dir, ".nojekyll")))
        for person in self.manager.data["people"]:
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "calendars", f"{person}.ics")))
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "c", f"{person}.html")))

if __name__ == '__main__':
    unittest.main()
