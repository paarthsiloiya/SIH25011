import pytest
from app.models import User, UserRole, Branch, Subject, Attendance, Marks, Enrollment, AssignedClass
from flask import url_for
from datetime import date, datetime, timezone

# --- Auth Tests ---
class TestAuth:
    def test_login_page_load(self, client):
        """Test login page loads successfully"""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b"Login" in response.data

    def test_login_success(self, client, auth, db):
        """Test successful login"""
        user = User(name="Test User", email="test@example.com", role=UserRole.STUDENT)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        response = auth.login("test@example.com", "password")
        assert response.status_code == 200
        assert b"Welcome back, Test User!" in response.data

    def test_login_failure(self, client, auth, db):
        """Test login with wrong password"""
        user = User(name="Test User", email="test@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        response = auth.login("test@example.com", "wrongpassword")
        assert response.status_code == 200
        assert b"Invalid email or password" in response.data

    def test_admin_login_redirect(self, client, auth, db):
        """Test admin redirects to admin dashboard"""
        user = User(name="Admin", email="admin@example.com", role=UserRole.ADMIN)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        response = auth.login("admin@example.com", "password")
        assert response.status_code == 200
        assert b"Admin" in response.data or b"Dashboard" in response.data

    def test_logout(self, client, auth, db):
        """Test logout functionality"""
        user = User(name="User", email="user@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        auth.login()
        response = client.get('/auth/logout', follow_redirects=True)       
        assert response.status_code == 200

# --- Security Tests ---
class TestSecurity:
    def test_student_cannot_access_admin(self, client, auth, db):
        """Test RBAC: Student cannot access admin dashboard"""
        user = User(name="Student", email="student@example.com", role=UserRole.STUDENT)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        auth.login("student@example.com", "password")
        response = client.get('/admin/dashboard')
        assert response.status_code in [403, 401, 302]

    def test_teacher_cannot_access_admin(self, client, auth, db):
        """Test RBAC: Teacher cannot access admin dashboard"""
        user = User(name="Teacher", email="teacher@example.com", role=UserRole.TEACHER)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        auth.login("teacher@example.com", "password")
        response = client.get('/admin/dashboard')
        assert response.status_code in [403, 401, 302]

# --- Models Tests ---
class TestModels:
    def test_user_creation(self, db):
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

    def test_institution_field(self, db):
        """Test that the institution field is working"""
        user = User(name="User", email="u@test.com", institution="DTC")
        user.set_password("pass")
        db.session.add(user)
        db.session.commit()
        
        assert user.institution == "DTC"
        
        user.institution = "New Inst"
        db.session.commit()
        
        fetched = db.session.get(User, user.id)
        assert fetched.institution == "New Inst"

    def test_attendance_stats_calculation(self, db):
        """Test attendance percentage calculation logic"""
        user = User(name="Student", email="student@example.com", role=UserRole.STUDENT, semester=1, branch=Branch.CSE)
        user.set_password("pass")
        subject = Subject(name="Math", code="MATH101", semester=1, branch="COMMON")
        db.session.add(user)
        db.session.add(subject)
        db.session.commit()

        records = [
            Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 1), status='present'),
            Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 2), status='present'),
            Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 3), status='present'),
            Attendance(user_id=user.id, subject_id=subject.id, date=date(2023, 1, 4), status='absent'),
        ]
        db.session.add_all(records)
        db.session.commit()

        stats = user.get_attendance_for_subject(subject.id)
        assert stats['total_classes'] == 4
        assert stats['attended_classes'] == 3
        assert stats['attendance_percentage'] == 75.0

    def test_marks_calculation(self, db):
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

    # --- New Tests Added ---

    def test_signup_email_already_exists(self, client, db):
        # Create user 1
        u1 = User(name="User 1", email="duplicate@test.com", role=UserRole.STUDENT)
        u1.set_password("password")
        db.session.add(u1)
        db.session.commit()
        
        # Try to signup with same email via POST (simulating signup form if available or direct creation)
        # Note: If signup is not public, we check logic or admin creation
        # Assuming admin creation or similar logic exists, or just DB integrity
        u2 = User(name="User 2", email="duplicate@test.com", role=UserRole.STUDENT)
        u2.set_password("password")
        db.session.add(u2)
        import sqlalchemy
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_login_nonexistent_user(self, auth):
        response = auth.login("ghost@test.com", "password")
        assert b"Invalid email or password" in response.data or b"Please check your login details" in response.data

    def test_user_repr(self):
        u = User(name="TestRep", email="rep@test.com", role=UserRole.ADMIN)
        assert "TestRep" in str(u)
        assert "rep@test.com" in str(u)

    def test_user_set_bad_password(self, db):
        u = User(name="NoPass", email="nopass@t.com", role=UserRole.STUDENT)
        # Should handle empty password gracefully or enforce it
        u.set_password("")
        db.session.add(u)
        db.session.commit()
        # Verify checking empty password matches
        assert u.check_password("") 
