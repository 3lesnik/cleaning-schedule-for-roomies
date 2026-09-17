#!/usr/bin/env python3
"""
Custom Cleaning Schedule Generator for your apartment

This script creates a 12-week cleaning schedule for your specific group
starting from next Monday, with tasks assigned to each person on Saturdays.
"""

from cleaning_schedule import create_cleaning_schedule
from generate_overview import generate_schedule_overview
import trash_bins
import datetime
import os

# Your custom tasks
tasks = [
    "Kitchen", 
    "Bathroom",
    "Downstairs Toilet", 
    "Floors duty",
    "Taking out trash", 
    "Communal laundry"
]

# Your group members (updated: Nicole -> Nancy, Gauresh -> Natan)
people = [
    "Nancy", 
    "Natan", 
    "Shlomo", 
    "Lucia", 
    "Tom", 
    "Ellie"
]

# Allow user to pick a start date
today = datetime.date.today()
next_monday = today
days_until_monday = 0 - today.weekday() + 7  # Calculate next Monday (0 = Monday, 6 = Sunday)
if days_until_monday <= 0:  # If today is Monday, go to next Monday
    days_until_monday += 7
next_monday = today + datetime.timedelta(days=days_until_monday)

# Default to Monday Aug 31, 2026 if today is in Sept 2026, so all trash dates are included
default_start_date = datetime.date(2026, 8, 31)

# Prompt for start date
use_custom_date = input(f"Would you like to set a custom start date? (default is {default_start_date.strftime('%Y-%m-%d')}) [y/N]: ").lower().strip()

if use_custom_date == 'y' or use_custom_date == 'yes':
    valid_date = False
    while not valid_date:
        date_input = input("Enter start date (YYYY-MM-DD): ")
        try:
            start_date = datetime.datetime.strptime(date_input, '%Y-%m-%d').date()
            valid_date = True
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD format.")
else:
    start_date = default_start_date
    print(f"Using default start date ({start_date.strftime('%Y-%m-%d')}) to align with trash pickup schedule.")

# Create output directory if it doesn't exist
output_dir = "schedules"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Base filename for the calendar files
base_filename = os.path.join(output_dir, "cleaning_schedule")

# Number of weeks: 18 weeks covers through end of December 2026
num_weeks = 18

# Generate the schedule with trash pickup integration
create_cleaning_schedule(
    tasks=tasks,
    people=people,
    start_date=start_date,
    num_weeks=num_weeks,
    output_file=f"{base_filename}.ics",
    calendar_name="Apartment Cleaning",
    trash_schedule=trash_bins.schedule
)

# Generate the schedule overview documents
text_file, html_file = generate_schedule_overview(
    tasks=tasks,
    people=people,
    start_date=start_date,
    num_weeks=num_weeks,
    output_dir=output_dir,
    trash_schedule=trash_bins.schedule
)

print(f"\nCleaning schedules created starting {start_date.strftime('%Y-%m-%d')} for {num_weeks} weeks")
print(f"Calendar files have been saved to the '{output_dir}' directory")
print("Overview documents created:")
print(f"- Text format: {text_file}")
print(f"- HTML format: {html_file} (open this in a web browser for a nicer view)")

# Print a simple text version of the first 4 weeks of the schedule
print("\nSummary of the first 4 weeks:")
print("=" * 60)

current_date = start_date
for week in range(4):
    saturday = current_date + datetime.timedelta(days=5)  # 5 days from Monday to Saturday
    print(f"\nWeek {week+1} (Saturday, {saturday.strftime('%B %d, %Y')})")
    print("-" * 60)
    
    for i, task in enumerate(tasks):
        person = people[(i + week) % len(people)]
        print(f"  {task}: {person}")
    
    current_date += datetime.timedelta(days=7)

print("\n" + "=" * 60)
print("Instructions:")
print("1. Send each person their specific calendar file:")
for person in people:
    filename = f"{base_filename}_{person.replace(' ', '_')}.ics"
    print(f"   - {filename} → Send to {person}")

print("\n2. Each person should import their file to their calendar app")
print("3. The overview document (HTML) can be shared with everyone")
print("4. All cleaning tasks are scheduled for Saturdays")
print("5. To update the schedule in the future, simply run this script again")
