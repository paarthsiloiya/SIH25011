import pytest
from datetime import datetime, date, timedelta
from app.models import User, UserRole, Branch, Subject, AssignedClass, Enrollment, EnrollmentStatus, Attendance, db as _db

# --- Fixtures for Setup ---

@pytest.fixture
def teacher_user(db):
    user = User(
        name="Teacher One", 
        email="teacher1@example.com", 
        role=UserRole.TEACHER,
        institution="DTC"
    )
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def other_teacher(db):
    user = User(
        name="Teacher Two", 
        email="teacher2@example.com", 
        role=UserRole.TEACHER,
        institution="DTC"
    )
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def student_user(db):
    user = User(
        name="Student One", 
        email="student1@example.com", 
        role=UserRole.STUDENT,
        enrollment_number="0011223344",
        semester=5,
        branch=Branch.CSE,
        institution="DTC"
    )
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def subject(db):
    subj = Subject(
        name="Data Structures and Algorithms",
        code="CSE-DSA",
        semester=5,
        branch="CSE",
        credits=4
    )
    db.session.add(subj)
    db.session.commit()
    return subj

@pytest.fixture
def assigned_class(db, teacher_user, subject):
    ac = AssignedClass(
        teacher_id=teacher_user.id,
        subject_id=subject.id,
        section="A"
    )
    db.session.add(ac)
    db.session.commit()
    return ac

@pytest.fixture
def enrollment(db, student_user, assigned_class):
    enrol = Enrollment(
        student_id=student_user.id,
        class_id=assigned_class.id,
        status=EnrollmentStatus.APPROVED
    )
    db.session.add(enrol)
    db.session.commit()
    return enrol

# --- Test Cases ---

def test_teacher_can_access_own_class(client, auth, teacher_user, assigned_class):
    auth.login(email=teacher_user.email, password="password")
    # Try accessing detailed view
    resp = client.get(f'/teacher/class/{assigned_class.id}')
    assert resp.status_code == 200
    assert b"Data Structures and Algorithms" in resp.data

def test_teacher_cannot_access_others_class(client, auth, other_teacher, assigned_class):
    auth.login(email=other_teacher.email, password="password")
    resp = client.get(f'/teacher/class/{assigned_class.id}', follow_redirects=True)
    # Should redirect or show error
    assert b"Unauthorized access" in resp.data

def test_student_cannot_access_class_details(client, auth, student_user, assigned_class):
    auth.login(email=student_user.email, password="password")
    resp = client.get(f'/teacher/class/{assigned_class.id}', follow_redirects=True)
    # Redirects to student dashboard or login
    assert resp.request.path != f'/teacher/class/{assigned_class.id}' 

def test_mark_attendance_post_success(client, auth, teacher_user, student_user, assigned_class, enrollment):
    auth.login(email=teacher_user.email, password="password")
    
    target_date = datetime.now().date().strftime('%Y-%m-%d')
    
    # Form data: attendance_{student_id} = 'on' for Present
    data = {
        'date': target_date,
        f'attendance_{student_user.id}': 'on'
    }
    
    resp = client.post(f'/teacher/class/{assigned_class.id}/attendance', data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Attendance marked" in resp.data
    
    # Verify in DB
    record = Attendance.query.filter_by(
        user_id=student_user.id,
        subject_id=assigned_class.subject_id,
        date=datetime.strptime(target_date, '%Y-%m-%d').date()
    ).first()
    
    assert record is not None
    assert record.status == 'present'

def test_mark_attendance_absent_implicit(client, auth, teacher_user, student_user, assigned_class, enrollment):
    """If checkbox is unchecked (missing in POST), status should be absent"""
    auth.login(email=teacher_user.email, password="password")
    
    target_date = "2025-01-01"
    
    # No checkbox data sent for student
    data = {
        'date': target_date
    }
    
    resp = client.post(f'/teacher/class/{assigned_class.id}/attendance', data=data, follow_redirects=True)
    assert resp.status_code == 200
    
    record = Attendance.query.filter_by(
        user_id=student_user.id,
        subject_id=assigned_class.subject_id,
        date=datetime.strptime(target_date, '%Y-%m-%d').date()
    ).first()
    
    assert record is not None
    assert record.status == 'absent'

def test_prevent_duplicate_attendance(client, auth, teacher_user, student_user, assigned_class, enrollment):
    auth.login(email=teacher_user.email, password="password")
    target_date = "2025-05-20"
    
    # 1. Mark initial attendance (Result: Present)
    with client.application.app_context():
        attendance = Attendance(
            user_id=student_user.id,
            subject_id=assigned_class.subject_id,
            date=datetime.strptime(target_date, '%Y-%m-%d').date(),
            status='present'
        )
        _db.session.add(attendance)
        _db.session.commit()
        
    # 2. Try to mark again (Attempting Absent)
    data = {'date': target_date} # Missing checkbox -> absent
    resp = client.post(f'/teacher/class/{assigned_class.id}/attendance', data=data, follow_redirects=True)
    
    # Should get error message
    assert b"Attendance for 2025-05-20 has already been marked" in resp.data
    
    # 3. Verify DB record is STILL 'present'
    record = Attendance.query.filter_by(
        user_id=student_user.id,
        subject_id=assigned_class.subject_id,
        date=datetime.strptime(target_date, '%Y-%m-%d').date()
    ).first()
    
    assert record.status == 'present'

def test_edit_class_details(client, auth, teacher_user, assigned_class):
    auth.login(email=teacher_user.email, password="password")
    
    # Check original section
    assert assigned_class.section == "A"
    
    # Update section
    resp = client.post(f'/teacher/class/{assigned_class.id}/edit', data={'section': 'B-Gamma'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Class details updated" in resp.data
    
    # Verify in DB
    updated_class = _db.session.get(AssignedClass, assigned_class.id)
    assert updated_class.section == "B-Gamma"

def test_download_report_csv(client, auth, teacher_user, student_user, assigned_class, enrollment):
    # Create some attendance data first so report isn't empty
    with client.application.app_context():
        att = Attendance(
            user_id=student_user.id,
            subject_id=assigned_class.subject_id,
            date=date(2025, 1, 1),
            status='present'
        )
        _db.session.add(att)
        _db.session.commit()

    auth.login(email=teacher_user.email, password="password")
    
    resp = client.get(f'/teacher/class/{assigned_class.id}/download')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'text/csv'
    
    # Check CSV Content
    content = resp.data.decode('utf-8')
    assert "Roll Number,Name,Total Classes,Attended,Percentage,Status" in content
    assert student_user.name in content
    # Should show 1 total, 1 attended
    assert "100.0%" in content  # 1/1
    # Check acronym generation implicitly via View? No, download CSV logic was separate.
    
def test_acronym_generation_in_views(client, auth, student_user, subject, assigned_class, enrollment):
    # Test the acronym logic specifically by checking chart labels in dashboard
    
    # Subject name: "Data Structures and Algorithms" -> Should be "DSA"
    # Create attendance so it shows up
    with client.application.app_context():
        att = Attendance(
            user_id=student_user.id,
            subject_id=subject.id,
            date=date(2025, 1, 1),
            status='present'
        )
        _db.session.add(att)
        _db.session.commit()
        
    auth.login(email=student_user.email, password="password")
    
# Check attendance page context or response data
    # Since we can't easily access context locals without extra setup,
    # we'll scan the rendered HTML/JSON data injected.
    resp = client.get('/attendance')
    assert resp.status_code == 200

    # Look for chart labels in the JSON script tag
    decoded = resp.data.decode('utf-8')

    # We are looking for the acronym "DSA" in the chart labels
    # The template renders: "attendanceChartData": {"labels": ["DSA"], ...}
    # But it might be escaped or formatted differently.
    # Searching for just "DSA" should be safe enough if it appears in the labels list.
    
    assert '"DSA"' in decoded or "'DSA'" in decoded
    
    # Test another subject "Programming In C" (assuming 'In' isn't in ignore list)
    # Let's create another subject
    with client.application.app_context():
        subj2 = Subject(name="Programming in C", code="CSE-PIC", semester=5, branch="CSE")
        _db.session.add(subj2)
        _db.session.flush()  # Ensure ID is generated
        
        # Need assignment/enrollment for it to appear? 
        # Dashboard logic: "current_user.get_subjects_with_attendance()"
        
        # Add attendance for it so it has data
        att2 = Attendance(
            user_id=student_user.id,
            subject_id=subj2.id,
            date=date(2025, 1, 2),
            status='present'
        )
        _db.session.add(att2)
        _db.session.commit()
    
    resp = client.get('/attendance')
    decoded = resp.data.decode('utf-8')
    
    # "Programming in C" -> "PIC" (P, I, C)
    assert '"PIC"' in decoded or "'PIC'" in decoded

def test_attendance_date_validation(client, auth, teacher_user, assigned_class):
    auth.login(email=teacher_user.email, password="password")
    
    # Invalid date format
    data = {'date': 'invalid-date'}
    resp = client.post(f'/teacher/class/{assigned_class.id}/attendance', data=data, follow_redirects=True)
    assert b"Invalid date format" in resp.data

