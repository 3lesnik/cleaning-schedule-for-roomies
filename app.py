#!/usr/bin/env python3
"""
Local Web Application for Cleaning Schedule, Trash Pickups, and House Events
"""

import os
import io
import datetime
import subprocess
from flask import Flask, render_template, jsonify, request, send_file, Response
from schedule_manager import ScheduleManager
import export_static

app = Flask(__name__)
manager = ScheduleManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/c/<person>')
@app.route('/roommate/<person>')
def roommate_page(person):
    """Personal shareable landing page for each roommate."""
    if person not in manager.data.get("people", []):
        return f"Roommate '{person}' not found.", 404
        
    cleanings = []
    trash_pickups = []
    
    for w in manager.data.get("weeks", []):
        for task, p in w.get("assignments", {}).items():
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
                
    house_events = []
    for he in manager.data.get("house_events", []):
        if he.get("target_audience") in ["all", person]:
            house_events.append(he)
            
    return render_template(
        'roommate.html',
        person=person,
        cleanings=cleanings,
        trash_pickups=trash_pickups,
        house_events=house_events
    )

@app.route('/calendars/<person>.ics')
def calendar_feed(person):
    """Direct live subscription feed for calendar apps (Apple, Google, Outlook)."""
    # If the user requested with or without .ics
    person_clean = person[:-4] if person.endswith('.ics') else person
    
    if person_clean not in manager.data.get("people", []):
        return Response("Person not found", status=404, mimetype="text/plain")
        
    ical_bytes = manager.generate_ical_for_person(person_clean)
    return Response(
        ical_bytes,
        mimetype="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="cleaning_schedule_{person_clean}.ics"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    return jsonify(manager.data)

@app.route('/api/reassign', methods=['POST'])
def reassign():
    req = request.get_json() or {}
    week_index = req.get('week_index')
    task = req.get('task')
    person = req.get('person')
    
    if week_index is None or not task or not person:
        return jsonify({"error": "Missing required fields"}), 400
        
    success = manager.reassign_task(int(week_index), task, person)
    if success:
        return jsonify({"status": "ok", "data": manager.data})
    return jsonify({"error": "Failed to reassign task"}), 400

@app.route('/api/swap', methods=['POST'])
def swap():
    req = request.get_json() or {}
    week_index = req.get('week_index')
    person1 = req.get('person1')
    person2 = req.get('person2')
    
    if week_index is None or not person1 or not person2:
        return jsonify({"error": "Missing required fields"}), 400
        
    success = manager.swap_tasks(int(week_index), person1, person2)
    if success:
        return jsonify({"status": "ok", "data": manager.data})
    return jsonify({"error": "Failed to swap tasks"}), 400

@app.route('/api/override_trash_pickup', methods=['POST'])
def override_trash_pickup():
    req = request.get_json() or {}
    date_str = req.get('date')
    assigned_to = req.get('assigned_to')
    
    if not date_str or not assigned_to:
        return jsonify({"error": "Missing date or assigned_to"}), 400
        
    success = manager.override_trash_pickup(date_str, assigned_to)
    if success:
        return jsonify({"status": "ok", "data": manager.data})
    return jsonify({"error": "Trash pickup date not found"}), 404

# --- House Events API ---
@app.route('/api/house_events', methods=['GET'])
def get_house_events():
    return jsonify(manager.get_house_events())

@app.route('/api/house_events', methods=['POST'])
def add_house_event():
    req = request.get_json() or {}
    title = req.get('title')
    date_str = req.get('date')
    time_str = req.get('time')
    description = req.get('description', '')
    target_audience = req.get('target_audience', 'all')
    
    if not title or not date_str:
        return jsonify({"error": "Title and date are required"}), 400
        
    event = manager.add_house_event(title, date_str, time_str, description, target_audience)
    return jsonify({"status": "ok", "event": event, "data": manager.data})

@app.route('/api/house_events/<event_id>', methods=['DELETE'])
def delete_house_event(event_id):
    success = manager.delete_house_event(event_id)
    if success:
        return jsonify({"status": "ok", "data": manager.data})
    return jsonify({"error": "Event not found"}), 404

# --- Preferences & Task Timing API ---
@app.route('/api/preferences', methods=['POST'])
def update_preferences():
    req = request.get_json() or {}
    person = req.get('person')
    day_of_week = req.get('day_of_week')
    time_str = req.get('time')
    
    if not person:
        return jsonify({"error": "Person is required"}), 400
        
    prefs = manager.update_person_preference(person, day_of_week, time_str)
    return jsonify({"status": "ok", "preferences": prefs, "data": manager.data})

@app.route('/api/task_schedule', methods=['POST'])
def adjust_task_schedule():
    req = request.get_json() or {}
    week_index = req.get('week_index')
    task = req.get('task')
    date_str = req.get('date')
    time_str = req.get('time')
    
    if week_index is None or not task:
        return jsonify({"error": "week_index and task are required"}), 400
        
    success = manager.adjust_task_schedule(int(week_index), task, date_str, time_str)
    if success:
        return jsonify({"status": "ok", "data": manager.data})
    return jsonify({"error": "Failed to adjust task schedule"}), 400

# --- Settings & Admin API ---
@app.route('/api/settings', methods=['POST'])
def update_settings():
    req = request.get_json() or {}
    start_date = req.get('start_date')
    num_weeks = req.get('num_weeks')
    people = req.get('people')
    tasks = req.get('tasks')
    default_cleaning_day = req.get('default_cleaning_day')
    default_cleaning_time = req.get('default_cleaning_time')
    person_preferences = req.get('person_preferences')
    
    if not start_date or not num_weeks:
        return jsonify({"error": "Missing start_date or num_weeks"}), 400
        
    data = manager.update_settings(
        start_date_str=start_date,
        num_weeks=int(num_weeks),
        people=people,
        tasks=tasks,
        default_cleaning_day=int(default_cleaning_day) if default_cleaning_day is not None else None,
        default_cleaning_time=default_cleaning_time,
        person_preferences=person_preferences,
        start_date=start_date
    )
    return jsonify({"status": "ok", "data": data})

@app.route('/api/reset', methods=['POST'])
def reset_schedule():
    data = manager.reset_to_rotation()
    return jsonify({"status": "ok", "data": data})

@app.route('/api/sync', methods=['POST'])
def sync_to_disk():
    files = manager.sync_to_filesystem()
    return jsonify({
        "status": "ok",
        "message": f"Successfully synchronized {len(files)} files to schedules/ directory!",
        "files": files
    })

@app.route('/api/export_gh_pages', methods=['POST'])
def export_gh_pages():
    try:
        docs_dir = export_static.generate_docs(manager)
        return jsonify({
            "status": "ok",
            "message": f"Successfully generated static site in '{docs_dir}/' for GitHub Pages!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/publish', methods=['POST'])
def publish_to_github():
    """Export static site, sync calendars, commit changes, and push to GitHub."""
    req = request.get_json() or {}
    commit_msg = req.get('message') or "Update cleaning schedule & calendar feeds"
    
    # 1. Regenerate static site in docs/ and sync schedules/
    try:
        docs_dir = export_static.generate_docs(manager)
        manager.sync_to_filesystem()
    except Exception as e:
        return jsonify({"error": f"Failed to generate static docs: {str(e)}"}), 500

    # 2. Git add and commit
    try:
        subprocess.run(["git", "add", "-A"], check=True)
        
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            
        # 3. Git push
        push_res = subprocess.run(
            ["git", "push", "origin", "main"], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        if push_res.returncode == 0:
            return jsonify({
                "status": "ok",
                "message": "🚀 Successfully exported and pushed to GitHub! Roommates' calendars will update in ~1 minute."
            })
        else:
            err_msg = (push_res.stderr or push_res.stdout or "Push error").strip()
            return jsonify({
                "status": "warning",
                "message": f"Saved and committed locally, but push failed ({err_msg}). Run 'git push' manually."
            })
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "warning",
            "message": "Push timed out (likely waiting for credentials). Run 'git push' in your terminal."
        })
    except Exception as e:
        return jsonify({"error": f"Git operation failed: {str(e)}"}), 500

@app.route('/api/export/<person>.ics', methods=['GET'])
def export_person(person):
    if person not in manager.data.get("people", []):
        return jsonify({"error": f"Person '{person}' not found"}), 404
        
    ical_bytes = manager.generate_ical_for_person(person)
    filename = f"cleaning_schedule_{person.replace(' ', '_')}.ics"
    
    return Response(
        ical_bytes,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/export/all.zip', methods=['GET'])
def export_all():
    zip_bytes = manager.export_all_zip()
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name="cleaning_schedules.zip"
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\n=======================================================")
    print(f" Cleaning Schedule & Trash Pickups Web App")
    print(f" Running at: http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=True)
