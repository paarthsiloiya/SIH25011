from app.models import User, UserRole, Subject, Branch, Attendance
from datetime import date

def test_student_dashboard_access(client, auth, db):
    """Test student can access dashboard"""
    user = User(name="Student", email="student@example.com", role=UserRole.STUDENT, branch=Branch.CSE, semester=1)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    auth.login("student@example.com", "password")
    
    # Assuming student dashboard is at /student/dashboard
    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b"Dashboard" in response.data

def test_unauthorized_dashboard_access(client):
    """Test accessing dashboard without login redirects to login"""
    response = client.get('/student/dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b"Login" in response.data or b"Please log in" in response.data

def test_attendance_view(client, auth, db):
    """Test student attendance view displays correctly"""
    user = User(name="Student", email="student@example.com", role=UserRole.STUDENT, branch=Branch.CSE, semester=1)
    user.set_password("password")
    
    subject = Subject(name="Programming in C", code="CSE-ES-101", semester=1, branch="CSE")
    db.session.add(user)
    db.session.add(subject)
    db.session.commit()

    # Add some attendance
    db.session.add(Attendance(user_id=user.id, subject_id=subject.id, date=date.today(), status='present'))
    db.session.commit()

    auth.login("student@example.com", "password")
    
    # Correct route is /attendance
    response = client.get('/attendance')
    assert response.status_code == 200
    assert b"Programming in C" in response.data
    assert b"100.0%" in response.data  # 1/1 present

def test_profile_settings(client, auth, db):
    """Test accessing settings page"""
    user = User(name="Student", email="student@example.com", role=UserRole.STUDENT)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    auth.login("student@example.com", "password")
    response = client.get('/settings') # or /student/settings depending on routes
    # Try generic or guess
    if response.status_code == 404:
        response = client.get('/student/settings')
    
    assert response.status_code == 200
    assert b"Settings" in response.data or b"Profile" in response.data
