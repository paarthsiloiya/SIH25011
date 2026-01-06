import pytest
from app.models import User, UserRole, Enrollment, Subject, AssignedClass
from flask import url_for
from datetime import datetime, timezone

class TestAdminViews:
    
    @pytest.fixture(autouse=True)
    def setup(self, db, client):
        # Create an admin user
        self.admin = User(name="Admin", email="admin@test.com", role=UserRole.ADMIN)
        self.admin.set_password("password")
        
        # Create a teacher
        self.teacher = User(name="Teacher", email="teacher@test.com", role=UserRole.TEACHER)
        self.teacher.set_password("password")
        
        # Create a student
        self.student = User(name="Student", email="student@test.com", role=UserRole.STUDENT)
        self.student.set_password("password")
        
        # Create a subject
        self.subject = Subject(name="Math", code="CSE-101", semester=1, branch="CSE")
        
        db.session.add_all([self.admin, self.teacher, self.student, self.subject])
        db.session.commit()
    
    def login_admin(self, client):
        return client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'password'}, follow_redirects=True)

    def test_admin_dashboard_access(self, client):
        self.login_admin(client)
        response = client.get('/admin/dashboard')
        assert response.status_code == 200
        assert b"Admin" in response.data or b"Dashboard" in response.data

    def test_admin_add_user(self, client, db):
        self.login_admin(client)
        data = {
            'name': 'New User',
            'email': 'new@test.com',
            'role': 'STUDENT',
            'password': 'password123',
            'phone': '1234567890',
            'semester': '1',
            'student_branch': 'CSE'
        }
        response = client.post('/admin/add_user', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"added successfully" in response.data
        
        user = User.query.filter_by(email='new@test.com').first()
        assert user is not None
        assert user.role == UserRole.STUDENT
    
    def test_admin_edit_user(self, client, db):
        self.login_admin(client)
        
        data = {
            'name': 'Updated Student',
            'phone': '9876543210',
            'semester': '2',
            'branch': 'CSE'
        }
        response = client.post(f'/admin/edit_user/{self.student.id}', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"User updated successfully" in response.data
        
        # Refresh from db
        updated_student = db.session.get(User, self.student.id)
        assert updated_student.name == 'Updated Student'
        assert updated_student.semester == 2

    def test_admin_assign_class(self, client, db):
        self.login_admin(client)
        
        # First ensure we have teacher and subject ids
        teacher_id = self.teacher.id
        subject_id = self.subject.id
        
        data = {
            'teacher_id': teacher_id,
            'subject_ids': [subject_id],
            'section': 'A'
        }
        
        response = client.post('/admin/assign_class', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"Successfully assigned" in response.data
        
        # Verify assignment
        assignment = AssignedClass.query.filter_by(teacher_id=teacher_id, subject_id=subject_id).first()
        assert assignment is not None
        assert assignment.section == 'A'

    def test_admin_delete_assignment(self, client, db):
        self.login_admin(client)
        
        # Create assignment first
        assign = AssignedClass(teacher_id=self.teacher.id, subject_id=self.subject.id, section='A')
        db.session.add(assign)
        db.session.commit()
        
        response = client.post(f'/admin/delete_assignment/{assign.id}', follow_redirects=True)
        assert response.status_code == 200
        assert b"Class assignment removed" in response.data
        
        assert db.session.get(AssignedClass, assign.id) is None

class TestTeacherViews:
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.teacher = User(name="Teacher", email="teacher@test.com", role=UserRole.TEACHER)
        self.teacher.set_password("password")
        
        self.student = User(name="Student", email="student@test.com", role=UserRole.STUDENT)
        self.student.set_password("password")
        
        self.subject = Subject(name="Math", code="CSE-101", semester=1, branch="CSE")
        
        db.session.add_all([self.teacher, self.student, self.subject])
        db.session.commit()
        
        # Assign class
        self.assignment = AssignedClass(teacher_id=self.teacher.id, subject_id=self.subject.id)
        db.session.add(self.assignment)
        db.session.commit()

    def login_teacher(self, client):
        return client.post('/auth/login', data={'email': 'teacher@test.com', 'password': 'password'}, follow_redirects=True)

    def test_teacher_dashboard(self, client):
        self.login_teacher(client)
        response = client.get('/teacher/dashboard')
        assert response.status_code == 200
    
    def test_teacher_classes(self, client):
        self.login_teacher(client)
        response = client.get('/teacher/classes')
        assert response.status_code == 200
        assert b"Math" in response.data # Subject name

    def test_teacher_enrollments(self, client, db):
        # Create enrollment request
        enrollment = Enrollment(student_id=self.student.id, class_id=self.assignment.id)
        db.session.add(enrollment)
        db.session.commit()
        
        self.login_teacher(client)
        response = client.get('/teacher/enrollments')
        assert response.status_code == 200
        # Should see student name
        assert self.student.name.encode() in response.data

    def test_teacher_handle_enrollment(self, client, db):
        enrollment = Enrollment(student_id=self.student.id, class_id=self.assignment.id)
        db.session.add(enrollment)
        db.session.commit()
        
        self.login_teacher(client)
        
        # Approve
        response = client.post(f'/teacher/enrollment/{enrollment.id}', data={'action': 'approve'}, follow_redirects=True)
        assert response.status_code == 200
        # Re-fetch enrollment (need to reset session or re-get)
        # Using db.session.get() if available or User.query.get
        # Since session might be expired, create new query
        e = db.session.get(Enrollment, enrollment.id)
        # Check status enum value or name
        # Using str() or .name/.value depending on implementation. In models it's Enum.
        # However SQLAlchemy Enum saves as name by default usually for sqlite if not native enum
        # Let's check string representation if that fails
        # Actually EnrollmentStatus is Python Enum. 
        # So e.status == EnrollmentStatus.APPROVED
        from app.models import EnrollmentStatus
        assert e.status == EnrollmentStatus.APPROVED

    def test_teacher_handle_enrollment_reject(self, client, db):
        enrollment = Enrollment(student_id=self.student.id, class_id=self.assignment.id)
        db.session.add(enrollment)
        db.session.commit()
        
        self.login_teacher(client)
        
        response = client.post(f'/teacher/enrollment/{enrollment.id}', data={'action': 'reject'}, follow_redirects=True)
        assert response.status_code == 200
        
        from app.models import EnrollmentStatus
        e = db.session.get(Enrollment, enrollment.id)
        assert e.status == EnrollmentStatus.REJECTED
