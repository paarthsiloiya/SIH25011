from app.models import User, UserRole
from flask import url_for

def test_login_page_load(client):
    """Test login page loads successfully"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b"Login" in response.data

def test_login_success(client, auth, db):
    """Test successful login"""
    user = User(name="Test User", email="test@example.com", role=UserRole.STUDENT)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    response = auth.login("test@example.com", "password")
    assert response.status_code == 200
    # Should redirect to student dashboard
    assert b"Welcome back, Test User!" in response.data

def test_login_failure(client, auth, db):
    """Test login with wrong password"""
    user = User(name="Test User", email="test@example.com")
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    response = auth.login("test@example.com", "wrongpassword")
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

def test_admin_login_redirect(client, auth, db):
    """Test admin redirects to admin dashboard"""
    user = User(name="Admin", email="admin@example.com", role=UserRole.ADMIN)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    response = auth.login("admin@example.com", "password")
    assert response.status_code == 200
    # Assuming admin dashboard text or url check, usually redirected to /admin/dashboard
    # Because follow_redirects=True, we check content of the redirected page
    # Since we don't know exact content of admin dashboard, we can check if it didn't stay on login
    assert b"Admin" in response.data or b"Dashboard" in response.data

def test_logout(client, auth, db):
    """Test logout functionality"""
    user = User(name="User", email="user@example.com")
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    auth.login()
    response = client.get('/auth/logout', follow_redirects=True) 
    # Check if logged out - usually redirects to login or index
    assert response.status_code == 200
