from flask import Blueprint, request, redirect, make_response, url_for, flash
from flask import render_template
from flask_login import login_required, current_user, logout_user
from .models import db, User, Branch, UserRole, Subject, AssignedClass, Enrollment, EnrollmentStatus
import json
import os
from datetime import datetime, timezone

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
    return redirect(url_for('auth.login'))

@views.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != UserRole.STUDENT:
        return redirect(url_for('auth.login'))

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
        
        # Check Enrollment & Assignments
        assigned_classes = AssignedClass.query.filter_by(subject_id=db_subject['id']).all()
        
        # Check if student is enrolled
        user_enrollment = Enrollment.query.filter(
            Enrollment.student_id == current_user.id,
            Enrollment.class_id.in_([cls.id for cls in assigned_classes]) if assigned_classes else False
        ).first()
        
        # Determine Faculty Name to display
        faculty_name = 'Not Assigned'
        if assigned_classes:
            if user_enrollment:
                faculty_name = user_enrollment.assigned_class.teacher.name
            elif len(assigned_classes) == 1:
                faculty_name = assigned_classes[0].teacher.name
            else:
                faculty_name = f"{len(assigned_classes)} Teachers Available"

        # Create merged subject data
        merged_subject = {
            'id': db_subject['id'],
            'name': db_subject['name'],
            'code': db_subject['code'],
            'faculty': faculty_name,
            'icon': json_subject.get('icon', 'https://img.icons8.com/ios/96/book--v1.png') if json_subject else 'https://img.icons8.com/ios/96/book--v1.png',
            'attendance_percentage': db_subject['attendance_percentage'],
            'total_classes': db_subject['total_classes'],
            'attended_classes': db_subject['attended_classes'],
            'status': db_subject['status'],
            'enrollment_status': user_enrollment.status.value if user_enrollment else 'NOT_ENROLLED',
            'assigned_classes': assigned_classes
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
        'institution': current_user.institution or 'Delhi Technical Campus',
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
        'institution': current_user.institution or 'Delhi Technical Campus',
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
    
    # Load calendar events
    calendar_events = load_calendar_events()
    
    rendered = render_template(
        "Student/attendance.html",
        subjects=subjects_data,
        attendance_stats=attendance_stats,
        missed_classes=missed_classes,
        attendance_chart_data=attendance_chart_data,
        calendar_events=calendar_events
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

@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Handle password change for all users
        if 'current_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.check_password(current_password):
                flash('Incorrect current password.', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
            else:
                current_user.set_password(new_password)
                current_user.is_password_changed = True
                db.session.commit()
                flash('Password updated successfully!', 'success')
            return redirect(url_for('views.settings'))

        # Handle profile update
        try:
            # Get form data (excluding name and email which are now read-only)
            phone = request.form.get('phone', '').strip()
            
            # Update common fields
            current_user.phone = phone if phone else None
            
            # Handle student-specific fields
            if current_user.role == UserRole.STUDENT:
                date_of_birth = request.form.get('date_of_birth')
                
                # Cannot change Enrollment Number or Branch
                # enrollment_number = request.form.get('enrollment_number', '').strip()
                # branch = request.form.get('branch', '').strip()
                
                semester = request.form.get('semester')
                institution = request.form.get('institution', '').strip()
                graduation_year = request.form.get('graduation_year')
                department = request.form.get('department', '').strip()
                
                # Validation (removed name and email validation since they're read-only)
                errors = []
                
                if semester and (not semester.isdigit() or int(semester) < 1 or int(semester) > 8):
                    errors.append('Please select a valid semester (1-8).')
                
                if graduation_year and not graduation_year.isdigit():
                    errors.append('Graduation year must be a valid number.')
                
                if errors:
                    for error in errors:
                        flash(error, 'error')
                    return redirect(url_for('views.settings'))
                
                # Handle date of birth
                if date_of_birth:
                    try:
                        current_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Invalid date format for date of birth.', 'error')
                        return redirect(url_for('views.settings'))
                
                # No update for enrollment_number or branch
                # current_user.enrollment_number = enrollment_number if enrollment_number else None
                
                if semester:
                    current_user.semester = int(semester)
                
                current_user.department = department if department else None
                
                # Handle institution
                current_user.institution = institution if institution else 'Delhi Technical Campus'
                
                # Handle graduation year - calculate year_of_admission
                if graduation_year:
                    grad_year = int(graduation_year)
                    current_user.year_of_admission = grad_year - 4  # Assuming 4-year degree

            elif current_user.role == UserRole.TEACHER:
                date_of_birth = request.form.get('date_of_birth')
                # Cannot change Branch or Department
                # branch = request.form.get('branch', '').strip()
                # department = request.form.get('department', '').strip()
                institution = request.form.get('institution', '').strip()
                
                errors = []
                # Removed validation for branch and department as they are read-only
                
                if errors:
                    for error in errors:
                        flash(error, 'error')
                    return redirect(url_for('views.settings'))
                
                if date_of_birth:
                    try:
                        current_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Invalid date format for date of birth.', 'error')
                        return redirect(url_for('views.settings'))
                
                # No update for branch or department
                
                current_user.institution = institution if institution else 'Delhi Technical Campus'

            # Update timestamp
            current_user.updated_at = datetime.now(timezone.utc)
            
            # Save to database
            db.session.commit()
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('views.settings'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {e}")
            flash('An error occurred while updating your profile. Please try again.', 'error')
            return redirect(url_for('views.settings'))
    
    # GET request - show settings form
    if current_user.role == UserRole.ADMIN:
        return render_template("Admin/settings.html")
    elif current_user.role == UserRole.TEACHER:
        teacher_data = {
            'name': current_user.name,
            'email': current_user.email,
            'phone': current_user.phone,
            'date_of_birth': current_user.date_of_birth.strftime('%Y-%m-%d') if current_user.date_of_birth else '',
            'branch': current_user.branch.value if current_user.branch else '',
            'department': current_user.department,
            'institution': current_user.institution or 'Delhi Technical Campus',
        }
        return render_template("Teacher/settings.html", teacher=teacher_data)

    # Use actual user data
    student_data = {
        'name': current_user.name,
        'email': current_user.email,
        'phone': current_user.phone,
        'date_of_birth': current_user.date_of_birth.strftime('%Y-%m-%d') if current_user.date_of_birth else '',
        'semester': current_user.semester,
        'branch': current_user.branch.value if current_user.branch else 'CSE',
        'enrollment_number': current_user.enrollment_number,
        'department': current_user.department,
        'institution': current_user.institution or 'Delhi Technical Campus',
        'graduation_year': current_user.year_of_admission + 4 if current_user.year_of_admission else '',
    }
    
    rendered = render_template(
        "Student/settings.html",
        student=student_data
    )
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Handle account deletion with proper data cleanup"""
    try:
        # Get confirmation input
        confirmation = request.form.get('confirmation', '').strip()
        
        # Debug logging
        print(f"🗑️ Account Deletion Request:")
        print(f"   User: {current_user.name} ({current_user.email})")
        print(f"   User ID: {current_user.id}")
        print(f"   Confirmation: '{confirmation}'")
        
        # Validate confirmation
        if confirmation != 'DELETE':
            flash('Account deletion failed. Please type "DELETE" exactly to confirm.', 'error')
            return redirect(url_for('views.settings'))
        
        # Store user info for logging before deletion
        user_name = current_user.name
        user_email = current_user.email
        user_id = current_user.id
        
        # Clean up related data first (if any exists in your schema)
        # You can add cleanup for attendance records, marks, etc. here
        # For example:
        # Attendance.query.filter_by(user_id=user_id).delete()
        # Marks.query.filter_by(user_id=user_id).delete()
        
        # Log out the user first
        logout_user()
        
        # Delete the user account
        user_to_delete = User.query.get(user_id)
        if user_to_delete:
            db.session.delete(user_to_delete)
            db.session.commit()
            
            print(f"✅ Account Deleted Successfully:")
            print(f"   User: {user_name} ({user_email})")
            print(f"   User ID: {user_id}")
            
            # Success message and redirect to home/login
            flash('Your account has been successfully deleted. Thank you for using our service.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Account deletion failed. User not found.', 'error')
            return redirect(url_for('auth.login'))
            
    except Exception as e:
        print(f"❌ Account Deletion Error: {str(e)}")
        db.session.rollback()
        flash('An error occurred while deleting your account. Please try again or contact support.', 'error')
        return redirect(url_for('views.settings'))

@views.route('/about')
@login_required
def about():
    rendered = render_template(
        "about.html"
    )
    
    response = make_response(rendered)
    return no_cache(response)
    
    response = make_response(rendered)
    return no_cache(response)

@views.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    section = request.args.get('section', 'view')
    search_query = request.args.get('search', '')
    
    query = User.query
    if search_query:
        query = query.filter(User.name.ilike(f'%{search_query}%') | User.email.ilike(f'%{search_query}%'))
        
    users = query.all()
    return render_template('Admin/dashboard.html', users=users, section=section, search_query=search_query)

@views.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
        
    user_to_edit = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            # Update basic info
            user_to_edit.name = request.form.get('name')
            # Email is read-only for now to prevent identity issues
            # user_to_edit.email = request.form.get('email') 
            user_to_edit.phone = request.form.get('phone')
            
            # Common fields for Student and Teacher
            date_of_birth = request.form.get('dob')
            if date_of_birth:
                try:
                    user_to_edit.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                except ValueError:
                    pass # Keep old date if invalid
            
            branch_str = request.form.get('branch')
            if branch_str:
                from .models import Branch
                try:
                    user_to_edit.branch = Branch(branch_str)
                except ValueError:
                    pass

            institution = request.form.get('institution')
            if institution:
                user_to_edit.institution = institution.strip()

            department = request.form.get('department')
            if department:
                user_to_edit.department = department.strip()

            # Role specific fields
            if user_to_edit.role == UserRole.STUDENT:
                user_to_edit.enrollment_number = request.form.get('enrollment_number')
                
                semester = request.form.get('semester')
                if semester:
                    user_to_edit.semester = int(semester)
                
                grad_year = request.form.get('graduation_year')
                if grad_year and grad_year.isdigit():
                    user_to_edit.year_of_admission = int(grad_year) - 4
            
            user_to_edit.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash('User updated successfully', 'success')
            return redirect(url_for('views.admin_dashboard', section='edit'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
            
    return render_template('Admin/edit_user.html', user=user_to_edit)

@views.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('Teacher/dashboard.html')

@views.route('/teacher/classes')
@login_required
def teacher_classes():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    assigned_classes = AssignedClass.query.filter_by(teacher_id=current_user.id).all()
    return render_template('Teacher/classes.html', assigned_classes=assigned_classes)

@views.route('/teacher/enrollments')
@login_required
def teacher_enrollments():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get all classes assigned to this teacher
    my_classes = AssignedClass.query.filter_by(teacher_id=current_user.id).all()
    
    grouped_requests = {}
    
    for cls in my_classes:
        # Get pending enrollments for this class
        pending = [e for e in cls.enrollments if e.status == EnrollmentStatus.PENDING]
        if pending:
            grouped_requests[cls] = pending
            
    return render_template('Teacher/enrollments.html', grouped_requests=grouped_requests)

@views.route('/teacher/enrollment/<int:id>', methods=['POST'])
@login_required
def handle_enrollment(id):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    enrollment = Enrollment.query.get_or_404(id)
    
    # Verify this enrollment belongs to a class taught by current user
    if enrollment.assigned_class.teacher_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('views.teacher_enrollments'))
        
    action = request.form.get('action')
    if action == 'approve':
        enrollment.status = EnrollmentStatus.APPROVED
        enrollment.response_date = datetime.now(timezone.utc)
        flash('Student enrollment approved.', 'success')
    elif action == 'reject':
        enrollment.status = EnrollmentStatus.REJECTED
        enrollment.response_date = datetime.now(timezone.utc)
        flash('Student enrollment rejected.', 'info')
        
    db.session.commit()
    return redirect(url_for('views.teacher_enrollments'))


@views.route('/student/join_class/<int:class_id>', methods=['POST'])
@login_required
def join_class(class_id):
    if current_user.role != UserRole.STUDENT:
        return redirect(url_for('views.student_dashboard'))
        
    assigned_class = AssignedClass.query.get_or_404(class_id)
    
    # Check if already enrolled
    existing = Enrollment.query.filter_by(student_id=current_user.id, class_id=class_id).first()
    if existing:
        flash('You have already requested to join this class.', 'warning')
    else:
        # Check if enrolled in another section of same subject? (Optional rule)
        # For now, allow requests.
        new_req = Enrollment(student_id=current_user.id, class_id=class_id)
        db.session.add(new_req)
        db.session.commit()
        flash('Enrollment request sent successfully!', 'success')
        
    return redirect(url_for('views.student_dashboard'))


@views.route('/admin/assign_class', methods=['GET', 'POST'])
@login_required
def assign_class():
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        subject_ids = request.form.getlist('subject_ids') # Checkbox list
        section = request.form.get('section')

        if not teacher_id or not subject_ids:
            flash('Please select a teacher and at least one subject.', 'error')
            return redirect(url_for('views.assign_class'))

        count = 0
        for sub_id in subject_ids:
            # Check if already assigned
            exists = AssignedClass.query.filter_by(teacher_id=teacher_id, subject_id=sub_id).first()
            if not exists:
                new_assign = AssignedClass(
                    teacher_id=teacher_id,
                    subject_id=sub_id,
                    section=section
                )
                db.session.add(new_assign)
                count += 1
        
        db.session.commit()
        flash(f'Successfully assigned {count} classes.', 'success')
        return redirect(url_for('views.assign_class'))

    # GET
    teachers = User.query.filter_by(role=UserRole.TEACHER).all()
    all_subjects = Subject.query.order_by(Subject.branch, Subject.semester, Subject.name).all()
    assignments = AssignedClass.query.order_by(AssignedClass.created_at.desc()).all()

    # Group subjects by Branch -> Semester for easier display
    grouped_subjects = {}  # { 'AIML': [sub1, sub2], ... }
    for sub in all_subjects:
        key = sub.branch
        if key not in grouped_subjects:
            grouped_subjects[key] = []
        grouped_subjects[key].append(sub)

    return render_template('Admin/assign_class.html', teachers=teachers, grouped_subjects=grouped_subjects, assignments=assignments)


@views.route('/admin/delete_assignment/<int:id>', methods=['POST'])
@login_required
def delete_assignment(id):
    if current_user.role != UserRole.ADMIN:
        flash('Access denied.', 'error')
        return redirect(url_for('auth.login'))
    
    assignment = AssignedClass.query.get_or_404(id)
    db.session.delete(assignment)
    db.session.commit()
    flash('Class assignment removed.', 'info')
    return redirect(url_for('views.assign_class'))


@views.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != UserRole.ADMIN:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name')
    email = request.form.get('email')
    role_str = request.form.get('role')
    password = request.form.get('password')
    
    if not all([name, email, role_str, password]):
        flash('All fields are required', 'error')
        return redirect(url_for('views.admin_dashboard'))
        
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'error')
        return redirect(url_for('views.admin_dashboard'))
        
    try:
        role = UserRole[role_str]
    except KeyError:
        flash('Invalid role', 'error')
        return redirect(url_for('views.admin_dashboard'))
        
    new_user = User(name=name, email=email, role=role)
    new_user.set_password(password)
    
    # Common additional fields
    phone = request.form.get('phone')
    if phone:
        new_user.phone = phone.strip()
        
    # Student specific fields
    if role == UserRole.STUDENT:
        # Get fields
        date_of_birth = request.form.get('student_dob')
        enrollment_number = request.form.get('enrollment_number')
        branch_str = request.form.get('student_branch')
        semester = request.form.get('semester')
        institution = request.form.get('student_institution')
        graduation_year = request.form.get('graduation_year')
        department = request.form.get('student_department')
        
        # Handle Date of Birth
        if date_of_birth:
            try:
                new_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format for date of birth', 'warning')
        
        # Handle Branch
        if branch_str:
            from .models import Branch
            try:
                new_user.branch = Branch(branch_str)
            except ValueError:
                flash('Invalid branch selected', 'warning')
                
        # Handle Semester
        if semester and semester.isdigit():
            new_user.semester = int(semester)
            
        # Handle Graduation Year -> Year of Admission
        if graduation_year and graduation_year.isdigit():
            new_user.year_of_admission = int(graduation_year) - 4
            
        # Other text fields
        if enrollment_number:
            new_user.enrollment_number = enrollment_number.strip()
        if institution:
            new_user.institution = institution.strip()
        if department:
            new_user.department = department.strip()

    # Teacher specific fields
    elif role == UserRole.TEACHER:
        # Get fields
        date_of_birth = request.form.get('teacher_dob')
        branch_str = request.form.get('teacher_branch')
        department = request.form.get('teacher_department')
        institution = request.form.get('teacher_institution')
        
        # Handle Date of Birth
        if date_of_birth:
            try:
                new_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format for date of birth', 'warning')
        
        # Handle Branch
        if branch_str:
            from .models import Branch
            try:
                new_user.branch = Branch(branch_str)
            except ValueError:
                flash('Invalid branch selected', 'warning')
        
        if department:
            new_user.department = department.strip()
        if institution:
            new_user.institution = institution.strip()
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'{role_str} added successfully', 'success')
    return redirect(url_for('views.admin_dashboard'))