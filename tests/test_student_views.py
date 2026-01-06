import pytest
from app.models import User, UserRole, Enrollment, Subject, AssignedClass
from flask import url_for
from datetime import datetime, date

class TestStudentAdvancedViews:
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.student = User(name="Student", email="student@test.com", role=UserRole.STUDENT, semester=1)
        self.student.set_password("password")
        
        self.subject = Subject(name="Math", code="CSE-101", semester=1, branch="CSE")
        self.teacher = User(name="Teacher", email="teacher@test.com", role=UserRole.TEACHER)
        self.teacher.set_password("password")
        
        db.session.add_all([self.student, self.teacher, self.subject])
        db.session.commit()
        
        self.assignment = AssignedClass(teacher_id=self.teacher.id, subject_id=self.subject.id)
        db.session.add(self.assignment)
        db.session.commit()

    def login_student(self, client):
        return client.post('/auth/login', data={'email': 'student@test.com', 'password': 'password'}, follow_redirects=True)

    def test_curriculum_view(self, client):
        self.login_student(client)
        response = client.get('/curriculum')
        assert response.status_code == 200
        assert b"Math" in response.data or b"CSE-101" in response.data

    def test_calendar_view(self, client):
        self.login_student(client)
        response = client.get('/calendar')
        assert response.status_code == 200
        # Check basic content presence
        assert b"Calendar" in response.data

    def test_student_join_class(self, client, db):
        self.login_student(client)
        
        response = client.post(f'/student/join_class/{self.assignment.id}', follow_redirects=True)
        assert response.status_code == 200
        assert b"Enrollment request sent" in response.data
        
        # Verify
        enrollment = Enrollment.query.filter_by(student_id=self.student.id, class_id=self.assignment.id).first()
        assert enrollment is not None

    def test_update_profile(self, client, db):
        self.login_student(client)
        
        data = {
            'phone': '1112223333',
            'semester': '2',
            'date_of_birth': '2000-01-01',
            'institution': 'New Inst'
        }
        
        response = client.post('/settings', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"Profile updated successfully" in response.data
        
        updated = db.session.get(User, self.student.id)
        assert updated.phone == '1112223333'
        assert updated.semester == 2
        assert updated.date_of_birth == date(2000, 1, 1)

    def test_change_password(self, client, db):
        self.login_student(client)
        
        data = {
            'current_password': 'password',
            'new_password': 'newpassword',
            'confirm_password': 'newpassword'
        }
        
        response = client.post('/settings', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"Password updated successfully" in response.data
        
        # Verify login with new password
        client.get('/auth/logout')
        response = client.post('/auth/login', data={'email': 'student@test.com', 'password': 'newpassword'}, follow_redirects=True)
        assert b"Welcome back" in response.data
        
    def test_change_password_fail_mismatch(self, client):
        self.login_student(client)
        data = {
            'current_password': 'password',
            'new_password': 'newpassword',
            'confirm_password': 'otherpassword'
        }
        response = client.post('/settings', data=data, follow_redirects=True)
        assert b"New passwords do not match" in response.data

    def test_change_password_fail_wrong_current(self, client):
        self.login_student(client)
        data = {
            'current_password': 'wrongpassword',
            'new_password': 'newpassword',
            'confirm_password': 'newpassword'
        }
        response = client.post('/settings', data=data, follow_redirects=True)
        assert b"Incorrect current password" in response.data
