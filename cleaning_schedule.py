#!/usr/bin/env python3
"""
Cleaning Schedule Generator

This script generates a cleaning schedule for 6 people rotating through 6 tasks.
It creates iCalendar files that can be imported into calendar apps on iPhone or Android.
Each task is scheduled as a one-day event on Saturdays.
"""

import argparse
import datetime
from icalendar import Calendar, Event
import uuid

def create_cleaning_schedule(tasks, people, start_date, num_weeks, output_file, calendar_name="Cleaning Schedule", trash_schedule=None, weekly_assignments=None):
    """
    Create a cleaning schedule and generate iCalendar files, one for each person.
    
    Args:
        tasks (list): List of cleaning tasks
        people (list): List of people
        start_date (datetime.date): Start date for the schedule
        num_weeks (int): Number of weeks to generate schedule for
        output_file (str): Path to output iCalendar file (a suffix will be added for each person)
        calendar_name (str): Base name of the calendar (visible in calendar apps)
        trash_schedule (list, optional): List of trash pickup dicts with 'date' and 'waste_type'
        weekly_assignments (list, optional): List of dicts mapping task -> person for each week
    """
    # Create a dictionary to store events for each person
    person_events = {person: [] for person in people}

    # Normalize trash_schedule if provided
    normalized_trash = []
    if trash_schedule:
        for entry in trash_schedule:
            pdate = entry['date']
            if isinstance(pdate, str):
                pdate = datetime.datetime.strptime(pdate, "%Y-%m-%d").date()
            normalized_trash.append({
                "date": pdate,
                "waste_type": entry.get("waste_type", "General Waste")
            })
    
    # Generate events for each week
    current_date = start_date
    for week in range(num_weeks):
        week_start = current_date
        week_end = current_date + datetime.timedelta(days=6)
        
        # Calculate Saturday for the cleaning task
        days_until_saturday = 5 - current_date.weekday()  # 5 = Saturday (0 = Monday, 6 = Sunday)
        if days_until_saturday < 0:  # If current_date is Sunday
            days_until_saturday += 7
        event_date = current_date + datetime.timedelta(days=days_until_saturday)
        
        week_trash_person = None

        for i, task in enumerate(tasks):
            # Rotate people for each task or use custom weekly assignments if provided
            if weekly_assignments and week < len(weekly_assignments) and task in weekly_assignments[week]:
                person = weekly_assignments[week][task]
            else:
                person = people[(i + week) % len(people)]
            
            if "trash" in task.lower():
                week_trash_person = person
            
            # Create event
            event = Event()
            event.add('summary', f"{task}")
            event.add('description', f"You are responsible for {task} this Saturday")
            event.add('dtstart', event_date)
            event.add('dtend', event_date + datetime.timedelta(days=1))  # End date is exclusive
            event['uid'] = str(uuid.uuid4())
            event.add('dtstamp', datetime.datetime.now())
            
            if person in person_events:
                person_events[person].append(event)
            else:
                person_events[person] = [event]
        
        # If there is a trash person and trash pickups during this week, add them
        if week_trash_person and normalized_trash:
            for pickup in normalized_trash:
                if week_start <= pickup["date"] <= week_end:
                    trash_event = Event()
                    waste = pickup["waste_type"]
                    trash_event.add('summary', f"Trash: {waste}")
                    trash_event.add('description', f"Trash pickup for {waste}. You are responsible for taking out the trash this week!")
                    trash_event.add('dtstart', pickup["date"])
                    trash_event.add('dtend', pickup["date"] + datetime.timedelta(days=1))
                    trash_event['uid'] = str(uuid.uuid4())
                    trash_event.add('dtstamp', datetime.datetime.now())
                    if week_trash_person in person_events:
                        person_events[week_trash_person].append(trash_event)
                    else:
                        person_events[week_trash_person] = [trash_event]
        
        # Move to next week
        current_date += datetime.timedelta(days=7)
    
    # Create a calendar file for each person
    output_files = []
    for person in people:
        # Create a new calendar for this person
        cal = Calendar()
        cal.add('prodid', '-//Cleaning Schedule Generator//github.com//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f"{calendar_name} - {person}")
        cal.add('x-wr-timezone', 'UTC')
        
        # Sort events chronologically
        events = person_events.get(person, [])
        events.sort(key=lambda ev: ev.get('dtstart').dt if ev.get('dtstart') else datetime.date.min)

        # Add all events for this person
        for event in events:
            cal.add_component(event)
        
        # Determine file name by adding the person's name before the extension
        if '.' in output_file:
            base, ext = output_file.rsplit('.', 1)
            person_file = f"{base}_{person.replace(' ', '_')}.{ext}"
        else:
            person_file = f"{output_file}_{person.replace(' ', '_')}"
        
        # Write calendar to file
        with open(person_file, 'wb') as f:
            f.write(cal.to_ical())
        
        output_files.append(person_file)
        print(f"Calendar for {person} saved to {person_file}")
    
    return output_files

def main():
    """Parse command-line arguments and run the schedule generator."""
    parser = argparse.ArgumentParser(description='Generate a cleaning schedule calendar file')
    parser.add_argument('--tasks', type=str, help='List of tasks separated by semicolons (;)')
    parser.add_argument('--people', type=str, help='List of people separated by semicolons (;)')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format', 
                        default=datetime.date.today().strftime('%Y-%m-%d'))
    parser.add_argument('--weeks', type=int, help='Number of weeks to generate', default=12)
    parser.add_argument('--output', type=str, help='Output file path', default='cleaning_schedule.ics')
    parser.add_argument('--calendar-name', type=str, help='Name of the calendar (visible in calendar apps)', 
                        default='Cleaning Schedule')
    
    args = parser.parse_args()
    
    # Check if tasks and people are provided
    if not args.tasks:
        tasks = input("Enter the cleaning tasks separated by semicolons (;): ")
        tasks = [task.strip() for task in tasks.split(';') if task.strip()]
    else:
        tasks = [task.strip() for task in args.tasks.split(';') if task.strip()]
    
    if not args.people:
        people = input("Enter the names of the 6 people separated by semicolons (;): ")
        people = [person.strip() for person in people.split(';') if person.strip()]
    else:
        people = [person.strip() for person in args.people.split(';') if person.strip()]
    
    # Validate inputs
    if len(tasks) != 6:
        print(f"Warning: Expected 6 tasks, got {len(tasks)}. Proceeding with the provided tasks.")
    
    if len(people) != 6:
        print(f"Warning: Expected 6 people, got {len(people)}. Proceeding with the provided people.")
    
    # Parse start date
    try:
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
    except ValueError:
        print("Invalid date format. Using today's date.")
        start_date = datetime.date.today()
    
    # Create the schedule
    create_cleaning_schedule(tasks, people, start_date, args.weeks, args.output, args.calendar_name)
    
    # Print some helpful instructions for managing the calendars
    print("\nIndividual calendars have been created for each person.")
    print("\nTo easily delete all events later:")
    print("1. In most calendar apps, look for calendars named: " + args.calendar_name + " - [Person's Name]")
    print("2. You can delete each calendar individually:")
    print("   - Apple Calendar: Go to Calendars > Edit > select the calendar > Delete")
    print("   - Google Calendar: Settings > [Calendar name] > Delete this calendar")
    print("   - Android: Open Calendar app > Settings > [Calendar name] > Delete calendar")
    print("\nSharing instructions:")
    print("1. Email or share each person's calendar file with them")
    print("2. Each person should import only their own calendar file")
    print("3. This way, everyone only sees their own assigned tasks")

if __name__ == "__main__":
    main()
