#!/usr/bin/env python3
"""
Cleaning Schedule Overview Generator

This script creates a text and HTML overview of the cleaning schedule,
showing who does what task each week with dates.
"""

import argparse
import datetime
import os

def generate_schedule_overview(tasks, people, start_date, num_weeks, output_dir="schedules", trash_schedule=None, weekly_assignments=None):
    """
    Generate a comprehensive overview of the cleaning schedule.
    
    Args:
        tasks (list): List of cleaning tasks
        people (list): List of people
        start_date (datetime.date): Start date for the schedule
        num_weeks (int): Number of weeks to generate schedule for
        output_dir (str): Directory to save the overview files
        trash_schedule (list, optional): Trash pickup entries
        weekly_assignments (list, optional): Custom assignments per week
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Normalize trash schedule
    normalized_trash = []
    if trash_schedule:
        for entry in trash_schedule:
            pdate = entry['date']
            if isinstance(pdate, str):
                pdate = datetime.datetime.strptime(pdate, "%Y-%m-%d").date()
            normalized_trash.append({
                "date": pdate,
                "waste_type": entry.get("waste_type", "Trash")
            })

    # Generate text overview
    text_file = os.path.join(output_dir, "cleaning_schedule_overview.txt")
    html_file = os.path.join(output_dir, "cleaning_schedule_overview.html")
    
    # Start generating the text overview
    with open(text_file, 'w') as f:
        f.write("CLEANING SCHEDULE OVERVIEW\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Start date: {start_date.strftime('%A, %B %d, %Y')}\n")
        f.write(f"Number of weeks: {num_weeks}\n\n")
        
        # Write header row for the table
        f.write(f"{'Week':<6} {'Date':<12} {'Person':<15} {'Task':<45}\n")
        f.write("-" * 80 + "\n")
        
        # Generate the schedule data
        current_date = start_date
        for week in range(num_weeks):
            week_start = current_date
            week_end = current_date + datetime.timedelta(days=6)

            # Calculate the Saturday of the current week
            days_until_saturday = 5 - current_date.weekday()
            if days_until_saturday < 0:
                days_until_saturday += 7
            
            saturday_date = current_date + datetime.timedelta(days=days_until_saturday)
            saturday_str = saturday_date.strftime("%Y-%m-%d")

            # Find pickups this week
            week_pickups = [p for p in normalized_trash if week_start <= p['date'] <= week_end]
            pickups_str = ""
            if week_pickups:
                pickups_str = " [" + ", ".join([f"{p['date'].strftime('%b %d')}: {p['waste_type']}" for p in week_pickups]) + "]"
            
            # For each task, determine who's responsible
            for i, task in enumerate(tasks):
                if weekly_assignments and week < len(weekly_assignments) and task in weekly_assignments[week]:
                    person = weekly_assignments[week][task]
                else:
                    person = people[(i + week) % len(people)]
                
                display_task = task
                if "trash" in task.lower() and pickups_str:
                    display_task = f"{task}{pickups_str}"
                
                # Write the row
                f.write(f"{week+1:<6} {saturday_str:<12} {person:<15} {display_task:<45}\n")
            
            # Add a separator between weeks
            f.write("-" * 80 + "\n")
            
            # Move to next week
            current_date += datetime.timedelta(days=7)
    
    # Generate HTML overview
    with open(html_file, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Cleaning Schedule Overview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 30px auto;
            max-width: 1000px;
            padding: 0 20px;
            color: #333;
            line-height: 1.6;
        }
        h1 {
            color: #1e293b;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
        }
        .info {
            margin-bottom: 20px;
            background: #f8fafc;
            padding: 15px 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background-color: #3b82f6;
            color: white;
            text-align: left;
            padding: 12px;
            font-size: 14px;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }
        tr.week-start {
            border-top: 2px solid #64748b;
        }
        tr:hover {
            background-color: #f1f5f9;
        }
        .trash-badge {
            display: inline-block;
            background: #e0f2fe;
            color: #0369a1;
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 9999px;
            margin: 2px 4px 2px 0;
            font-weight: 500;
        }
        @media print {
            body { font-size: 11pt; }
            h1 { font-size: 16pt; }
            table { font-size: 9pt; }
        }
    </style>
</head>
<body>
    <h1>Cleaning Schedule Overview</h1>
    <div class="info">
        <p><strong>Start date:</strong> """)
        f.write(start_date.strftime("%A, %B %d, %Y"))
        f.write(f"""</p>
        <p><strong>Number of weeks:</strong> {num_weeks}</p>
    </div>
    
    <table>
        <tr>
            <th>Week</th>
            <th>Saturday Cleaning</th>
            <th>Person</th>
            <th>Task</th>
        </tr>
""")
        
        # Generate the schedule data for HTML
        current_date = start_date
        for week in range(num_weeks):
            week_start = current_date
            week_end = current_date + datetime.timedelta(days=6)

            days_until_saturday = 5 - current_date.weekday()
            if days_until_saturday < 0:
                days_until_saturday += 7
            
            saturday_date = current_date + datetime.timedelta(days=days_until_saturday)
            saturday_str = saturday_date.strftime("%B %d, %Y")

            week_pickups = [p for p in normalized_trash if week_start <= p['date'] <= week_end]
            
            for i, task in enumerate(tasks):
                if weekly_assignments and week < len(weekly_assignments) and task in weekly_assignments[week]:
                    person = weekly_assignments[week][task]
                else:
                    person = people[(i + week) % len(people)]

                task_html = f"<strong>{task}</strong>"
                if "trash" in task.lower() and week_pickups:
                    badges = "".join([f'<span class="trash-badge">🗑️ {p["date"].strftime("%b %d")}: {p["waste_type"]}</span>' for p in week_pickups])
                    task_html += f"<div style='margin-top:4px;'>{badges}</div>"
                
                if i == 0:
                    f.write(f"""        <tr class="week-start">
            <td><strong>Week {week+1}</strong></td>
            <td>{saturday_str}</td>
            <td><strong>{person}</strong></td>
            <td>{task_html}</td>
        </tr>
""")
                else:
                    f.write(f"""        <tr>
            <td></td>
            <td></td>
            <td><strong>{person}</strong></td>
            <td>{task_html}</td>
        </tr>
""")
            
            current_date += datetime.timedelta(days=7)
        
        f.write("""    </table>
    <div class="info" style="margin-top: 20px;">
        <p><em>Note: Regular cleaning tasks are scheduled for Saturdays. Trash pickup events are scheduled for specific pickup days throughout the week.</em></p>
        <p><em>Individual calendar files (.ics) are available for each person.</em></p>
    </div>
</body>
</html>""")
    
    return text_file, html_file

def main():
    """Parse command-line arguments and generate the schedule overview."""
    parser = argparse.ArgumentParser(description='Generate a cleaning schedule overview document')
    parser.add_argument('--tasks', type=str, help='List of tasks separated by semicolons (;)')
    parser.add_argument('--people', type=str, help='List of people separated by semicolons (;)')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format', 
                       default=datetime.date.today().strftime('%Y-%m-%d'))
    parser.add_argument('--weeks', type=int, help='Number of weeks to generate', default=12)
    parser.add_argument('--output-dir', type=str, help='Output directory', default='schedules')
    
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
    
    # Parse start date
    try:
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
    except ValueError:
        print("Invalid date format. Using today's date.")
        start_date = datetime.date.today()
    
    # Generate the overview
    text_file, html_file = generate_schedule_overview(tasks, people, start_date, args.weeks, args.output_dir)
    
    print("\nSchedule overview files created:")
    print(f"- Text format: {text_file}")
    print(f"- HTML format: {html_file} (open this in a web browser for a nicer view)")
    print("\nThe HTML file can be printed or shared with everyone as a reference.")

if __name__ == "__main__":
    main()