from flask import Blueprint, request, redirect, make_response
from flask import render_template
from flask_login import login_required, current_user
import json
import os
from datetime import datetime

views = Blueprint('views', __name__)

# Add cache busting for JSON data
def no_cache(response):
    """Add headers to prevent caching"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def load_semester_data():
    """Load branch-specific semester data from JSON file"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'branch_subjects.json')
    try:
        # Force fresh read of the file
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        print(f"✅ Loaded fresh branch-specific JSON data - {len(data.get('branches', {}))} branches found")
        return data
    except FileNotFoundError:
        print("❌ branch_subjects.json file not found, using fallback data")
        # Fallback data if JSON file not found
        return {
            "branches": {
                "CSE": {
                    "name": "Computer Science & Engineering",
                    "semesters": {
                        "1": [
                            {
                                'name': 'Programming In C',
                                'faculty': 'Rachna Sharma',
                                'icon': 'https://img.icons8.com/pulsar-line/96/code.png',
                                'code': 'ES-101',
                                'credits': 3
                            }
                        ]
                    }
                }
            }
        }

def load_calendar_events():
    """Load calendar events from JSON file"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'calendar_events.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        events = data.get('events', {})
        recurring_events = data.get('recurring_events', {})
        
        # Add recurring events for current year
        current_year = datetime.now().year
        for date, event in recurring_events.items():
            events[f"{current_year}-{date}"] = event
        
        # Add recurring events for next year if we're in December
        if datetime.now().month == 12:
            next_year = current_year + 1
            for date, event in recurring_events.items():
                events[f"{next_year}-{date}"] = event
        
        return events
    except FileNotFoundError:
        # Fallback to empty dict if JSON file not found
        return {}

@views.route('/')
def home():
    return redirect('/dashboard')

@views.route('/dashboard')
@login_required
def dashboard():
    # Load branch-specific data from JSON
    json_data = load_semester_data()
    
    # Get real subjects and attendance data from database (now branch-aware)
    db_subjects_data = current_user.get_subjects_with_attendance()
    
    user_branch = current_user.branch.value if current_user.branch else 'CSE'
    print(f"🔍 Debug Info for User: {current_user.name} (Semester {current_user.semester}) (Branch {user_branch})")
    print(f"📊 Database subjects found: {len(db_subjects_data)}")
    for db_subj in db_subjects_data:
        print(f"   DB: {db_subj['code']} - {db_subj['name']}")
    
    # Merge database data with JSON data for icons and faculty
    subjects_data = []
    
    # Get branch-specific subjects from JSON
    branch_data = json_data.get('branches', {}).get(user_branch, {})
    semester_subjects = branch_data.get('semesters', {}).get(str(current_user.semester), [])
    
    print(f"📚 JSON subjects found for {user_branch} Semester {current_user.semester}: {len(semester_subjects)}")
    
    for db_subject in db_subjects_data:
        # Find matching subject in JSON data (match by base code, ignoring branch prefix)
        json_subject = None
        db_base_code = db_subject['code'].split('-', 1)[-1] if '-' in db_subject['code'] else db_subject['code']
        
        for js in semester_subjects:
            if js['code'] == db_base_code or js['code'] in db_subject['code']:
                json_subject = js
                break
        
        if not json_subject:
            print(f"❌ No JSON match found for DB subject: {db_subject['code']}")
        
        # Create merged subject data
        merged_subject = {
            'id': db_subject['id'],
            'name': db_subject['name'],
            'code': db_subject['code'],
            'faculty': json_subject.get('faculty', 'Faculty Name') if json_subject else 'Faculty Name',
            'icon': json_subject.get('icon', 'https://img.icons8.com/ios/96/book--v1.png') if json_subject else 'https://img.icons8.com/ios/96/book--v1.png',
            'attendance_percentage': db_subject['attendance_percentage'],
            'total_classes': db_subject['total_classes'],
            'attended_classes': db_subject['attended_classes'],
            'status': db_subject['status']
        }
        subjects_data.append(merged_subject)
    
    # Get real attendance statistics
    attendance_stats = current_user.get_overall_attendance_stats()
    
    # Use actual user data
    student_data = {
        'name': current_user.name,
        'email': current_user.email,
        'phone': current_user.phone or 'Not provided',
        'semester': current_user.semester,
        'branch': current_user.branch.value if current_user.branch else 'Not provided',
        'enrollment_number': current_user.enrollment_number or 'Not provided',
        'department': current_user.department or 'Not provided',
        'institution': 'Delhi Technical University',  # You can make this configurable
        'graduation_year': current_user.year_of_admission + 4 if current_user.year_of_admission else 'Not set',
        'role': 'Student',
        'location': 'Delhi',  # You can add this field to User model if needed
        'profile_image': 'profile.jpg'
    }
    
    # Get semester info
    semester_info = f"Semester {current_user.semester}"
    
    # Generate missed classes data from actual attendance (if any)
    missed_classes = []
    for subject in subjects_data:
        if subject['total_classes'] > 0:
            missed_count = subject['total_classes'] - subject['attended_classes']
            if missed_count > 0:
                missed_classes.append({
                    'subject': subject['code'],
                    'missed_count': missed_count,
                    'backlog_item': f'{missed_count} Classes Missed'
                })
    
    # If no real data, show empty state
    if not missed_classes:
        missed_classes = [
            {'subject': 'No Data', 'missed_count': 0, 'backlog_item': 'Start attending classes to track'}
        ]
    
    # Static data that doesn't depend on semester
    missed_classes = [
        {'subject': 'DS', 'missed_count': 4, 'backlog_item': '1 Assignment'},
        {'subject': 'OS', 'missed_count': 3, 'backlog_item': 'Lab Record'},
        {'subject': 'CN', 'missed_count': 2, 'backlog_item': 'Project Work'}
    ]
    # Generate dynamic notifications based on actual attendance
    notifications = []
    
    # Add attendance-based notifications
    for subject in subjects_data:
        if subject['attendance_percentage'] < 75 and subject['total_classes'] > 0:
            notifications.append({
                'icon': '⚠️',
                'message': f'Low attendance in {subject["code"]}: {subject["attendance_percentage"]}%',
                'bg_class': 'bg-red-100 text-red-700'
            })
    
    # Add default notifications if no attendance data
    if not notifications:
        notifications = [
            {
                'icon': '📚',
                'message': 'Welcome! Start attending classes to track your progress',
                'bg_class': 'bg-blue-100 text-blue-700'
            },
            {
                'icon': '🎯',
                'message': 'Set up your attendance goals and stay on track',
                'bg_class': 'bg-green-100 text-green-700'
            }
        ]
    
    upcoming_events = [
        {'date': '15 Sept', 'title': 'Mid Sem Exams Begin'},
        {'date': '30 Sept', 'title': 'Project Submission'},
        {'date': '15 Dec', 'title': 'End Semester Exams'}
    ]
    
    # Generate chart data from subjects - handle empty data
    if subjects_data:
        attendance_chart_data = {
            'labels': [subject['name'][:3].upper() for subject in subjects_data],
            'data': [subject['attendance_percentage'] for subject in subjects_data]
        }
    else:
        attendance_chart_data = {
            'labels': ['No Data'],
            'data': [0]
        }
    
    calendar_events = load_calendar_events()
    
    # Render template and create response with cache-busting headers
    rendered = render_template(
        "Student/dashboard.html",
        student=student_data,
        subjects=subjects_data,
        semester_info=semester_info,
        attendance_stats=attendance_stats,
        missed_classes=missed_classes,
        notifications=notifications,
        upcoming_events=upcoming_events,
        attendance_chart_data=attendance_chart_data,
        calendar_events=calendar_events
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/curriculum')
@login_required
def curriculum():
    # Load branch-specific data from JSON
    json_data = load_semester_data()
    
    # Get real subjects data from database
    db_subjects_data = current_user.get_subjects_with_attendance()
    
    user_branch = current_user.branch.value if current_user.branch else 'CSE'
    
    # Merge database data with JSON data for icons and faculty
    subjects_data = []
    
    # Get branch-specific subjects from JSON
    branch_data = json_data.get('branches', {}).get(user_branch, {})
    semester_subjects = branch_data.get('semesters', {}).get(str(current_user.semester), [])
    
    for db_subject in db_subjects_data:
        # Find matching subject in JSON data
        json_subject = None
        db_base_code = db_subject['code'].split('-', 1)[-1] if '-' in db_subject['code'] else db_subject['code']
        
        for js in semester_subjects:
            if js['code'] == db_base_code or js['code'] in db_subject['code']:
                json_subject = js
                break
        
        # Create merged subject data
        merged_subject = {
            'id': db_subject['id'],
            'name': db_subject['name'],
            'code': db_subject['code'],
            'faculty': json_subject.get('faculty', 'Faculty Name') if json_subject else 'Faculty Name',
            'icon': json_subject.get('icon', 'https://img.icons8.com/ios/96/book--v1.png') if json_subject else 'https://img.icons8.com/ios/96/book--v1.png',
        }
        subjects_data.append(merged_subject)
    
    # Use actual user data
    student_data = {
        'name': current_user.name,
        'email': current_user.email,
        'phone': current_user.phone or 'Not provided',
        'semester': current_user.semester,
        'branch': current_user.branch.value if current_user.branch else 'Not provided',
        'enrollment_number': current_user.enrollment_number or 'Not provided',
        'department': current_user.department or 'Not provided',
        'institution': 'Delhi Technical University',
        'graduation_year': current_user.year_of_admission + 4 if current_user.year_of_admission else 'Not set',
    }
    
    # Get semester info
    semester_info = f"Semester {current_user.semester}"
    
    rendered = render_template(
        "Student/curriculum.html",
        student=student_data,
        subjects=subjects_data,
        semester_info=semester_info
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/attendance')
@login_required
def attendance():
    # Load branch-specific data from JSON
    json_data = load_semester_data()
    
    # Get real subjects and attendance data from database
    db_subjects_data = current_user.get_subjects_with_attendance()
    
    user_branch = current_user.branch.value if current_user.branch else 'CSE'
    
    # Merge database data with JSON data for icons and faculty
    subjects_data = []
    
    # Get branch-specific subjects from JSON
    branch_data = json_data.get('branches', {}).get(user_branch, {})
    semester_subjects = branch_data.get('semesters', {}).get(str(current_user.semester), [])
    
    for db_subject in db_subjects_data:
        # Find matching subject in JSON data
        json_subject = None
        db_base_code = db_subject['code'].split('-', 1)[-1] if '-' in db_subject['code'] else db_subject['code']
        
        for js in semester_subjects:
            if js['code'] == db_base_code or js['code'] in db_subject['code']:
                json_subject = js
                break
        
        # Create merged subject data
        merged_subject = {
            'id': db_subject['id'],
            'name': db_subject['name'],
            'code': db_subject['code'],
            'faculty': json_subject.get('faculty', 'Faculty Name') if json_subject else 'Faculty Name',
            'icon': json_subject.get('icon', 'https://img.icons8.com/ios/96/book--v1.png') if json_subject else 'https://img.icons8.com/ios/96/book--v1.png',
            'attendance_percentage': db_subject['attendance_percentage'],
            'total_classes': db_subject['total_classes'],
            'attended_classes': db_subject['attended_classes'],
            'status': db_subject['status']
        }
        subjects_data.append(merged_subject)
    
    # Get real attendance statistics
    attendance_stats = current_user.get_overall_attendance_stats()
    
    # Generate missed classes data from actual attendance
    missed_classes = []
    for subject in subjects_data:
        if subject['total_classes'] > 0:
            missed_count = subject['total_classes'] - subject['attended_classes']
            if missed_count > 0:
                missed_classes.append({
                    'subject': subject['code'],
                    'missed_count': missed_count,
                    'backlog_item': f'{missed_count} Classes Missed'
                })
    
    # If no real data, show placeholder
    if not missed_classes:
        missed_classes = [
            {'subject': 'No Data', 'missed_count': 0, 'backlog_item': 'Start attending classes to track'}
        ]
    
    # Generate chart data from subjects
    if subjects_data:
        attendance_chart_data = {
            'labels': [subject['name'][:3].upper() for subject in subjects_data],
            'data': [subject['attendance_percentage'] for subject in subjects_data]
        }
    else:
        attendance_chart_data = {
            'labels': ['No Data'],
            'data': [0]
        }
    
    rendered = render_template(
        "Student/attendance.html",
        subjects=subjects_data,
        attendance_stats=attendance_stats,
        missed_classes=missed_classes,
        attendance_chart_data=attendance_chart_data
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/calendar')
@login_required
def calendar():
    calendar_events = load_calendar_events()
    
    rendered = render_template(
        "Student/calendar.html",
        calendar_events=calendar_events
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/settings')
@login_required
def settings():
    # Use actual user data
    student_data = {
        'name': current_user.name,
        'email': current_user.email,
        'phone': current_user.phone,
        'date_of_birth': current_user.date_of_birth,
        'semester': current_user.semester,
        'branch': current_user.branch.value if current_user.branch else 'CSE',
        'enrollment_number': current_user.enrollment_number,
        'department': current_user.department,
        'institution': 'Delhi Technical University',
        'graduation_year': current_user.year_of_admission + 4 if current_user.year_of_admission else None,
    }
    
    rendered = render_template(
        "Student/settings.html",
        student=student_data
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/about')
@login_required
def about():
    rendered = render_template(
        "Student/about.html"
    )
    
    response = make_response(rendered)
    return no_cache(response)