from app.models import User, Branch, UserRole, Subject, Attendance, Marks
from datetime import date, datetime

def test_user_creation(db):
    """Test user creation and password hashing"""
    user = User(
        name="Test Student",
        email="test@example.com",
        role=UserRole.STUDENT,
        branch=Branch.CSE,
        semester=1
    )
    user.set_password("securepassword")
    db.session.add(user)
    db.session.commit()

    assert user.id is not None
    assert user.name == "Test Student"
    assert user.email == "test@example.com"
    assert user.check_password("securepassword")
    assert not user.check_password("wrongpassword")
    assert user.role == UserRole.STUDENT
    assert user.branch == Branch.CSE

def test_attendance_stats_calculation(db):
    """Test attendance percentage calculation logic"""
    # Create User
    # Need to set semester and branch so get_subjects_for_semester works
    user = User(
        name="Student", 
        email="student@example.com", 
        role=UserRole.STUDENT,
        semester=1,
        branch=Branch.CSE
    )
    user.set_password("pass")
    
    # Create Subject
    # Subject must match user's semester and branch (or be COMMON)
    subject = Subject(name="Math", code="MATH101", semester=1, branch="COMMON")
    db.session.add(user)
    db.session.add(subject)
    db.session.commit()

    # Create Attendance Records
    # 3 present, 1 absent = 4 total, 75% attendance
    records = [
        Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 1), status='present'),
        Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 2), status='present'),
        Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 3), status='present'),
        Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 4), status='absent'),
    ]
    db.session.add_all(records)
    db.session.commit()

    # Test get_attendance_for_subject
    stats = user.get_attendance_for_subject(subject.id)
    assert stats['total_classes'] == 4
    assert stats['attended_classes'] == 3
    assert stats['attendance_percentage'] == 75.0
    assert stats['status'] == 'good'

    # Test get_overall_attendance_stats
    # (Only one subject so it should be same)
    overall = user.get_overall_attendance_stats()
    assert overall['total_classes'] == 4
    assert overall['attended_classes'] == 3
    assert overall['attendance_percentage'] == 75.0
    assert overall['needed_for_75'] == 0

def test_marks_calculation(db):
    """Test marks percentage and grade calculation"""
    user = User(name="Student", email="student@example.com")
    user.set_password("securepassword")
    subject = Subject(name="Math", code="MATH101", semester=1)
    db.session.add_all([user, subject])
    db.session.commit()

    mark = Marks(
        user_id=user.id,
        subject_id=subject.id,
        assessment_type="midterm",
        assessment_name="Mid Term 1",
        max_marks=100.0,
        obtained_marks=85.0
    )
    db.session.add(mark)
    db.session.commit()

    assert mark.percentage == 85.0
    assert mark.grade == 'A'

    mark.obtained_marks = 45.0
    assert mark.grade == 'D'
    
    mark.obtained_marks = 95.0
    assert mark.grade == 'A+'
