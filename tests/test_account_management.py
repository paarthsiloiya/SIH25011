import pytest
from app.models import User, UserRole
from flask import url_for

class TestAccountManagement:
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.user = User(name="User To Delete", email="delete@test.com", role=UserRole.STUDENT)
        self.user.set_password("password")
        db.session.add(self.user)
        db.session.commit()

    def test_delete_account_success(self, client):
        client.post('/auth/login', data={'email': 'delete@test.com', 'password': 'password'})
        
        # Confirm delete
        response = client.post('/delete_account', data={'confirmation': 'DELETE'}, follow_redirects=True)
        assert response.status_code == 200
        assert b"account has been successfully deleted" in response.data
        
        # Check user is gone
        assert User.query.filter_by(email='delete@test.com').first() is None

    def test_delete_account_fail_wrong_confirmation(self, client):
        client.post('/auth/login', data={'email': 'delete@test.com', 'password': 'password'})
        
        response = client.post('/delete_account', data={'confirmation': 'WRONG'}, follow_redirects=True)
        assert response.status_code == 200
        assert b"Account deletion failed" in response.data
        
        # User still exists
        assert User.query.filter_by(email='delete@test.com').first() is not None

class TestAdminAddUserDetailed:
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.admin = User(name="Admin", email="admin@test.com", role=UserRole.ADMIN)
        self.admin.set_password("password")
        db.session.add(self.admin)
        db.session.commit()

    def login_admin(self, client):
        return client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'password'}, follow_redirects=True)

    def test_add_teacher_with_details(self, client):
        self.login_admin(client)
        data = {
            'name': 'New Teacher',
            'email': 'newteacher@test.com',
            'role': 'TEACHER',
            'password': 'password',
            'phone': '1231231234',
            'teacher_branch': 'CSE',
            'teacher_institution': 'DTC',
            'teacher_department': 'CS Dept'
        }
        response = client.post('/admin/add_user', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b"TEACHER added successfully" in response.data
        
        teacher = User.query.filter_by(email='newteacher@test.com').first()
        assert teacher.institution == 'DTC'
        assert teacher.department == 'CS Dept'

    def test_add_existing_user_fail(self, client):
        self.login_admin(client)
        data = {
            'name': 'Duplicate',
            'email': 'admin@test.com', # Existing email
            'role': 'STUDENT',
            'password': 'password'
        }
        response = client.post('/admin/add_user', data=data, follow_redirects=True)
        assert b"Email already exists" in response.data

    def test_add_user_missing_fields(self, client):
        self.login_admin(client)
        data = {
            'name': 'Incomplete',
            # missing email and password
        }
        response = client.post('/admin/add_user', data=data, follow_redirects=True)
        assert b"All fields are required" in response.data
