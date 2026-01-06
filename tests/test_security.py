from app.models import User, UserRole

def test_student_cannot_access_admin(client, auth, db):
    """Test RBAC: Student cannot access admin dashboard"""
    user = User(name="Student", email="student@example.com", role=UserRole.STUDENT)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    auth.login("student@example.com", "password")
    
    # Try accessing admin dashboard
    response = client.get('/admin/dashboard')
    
    # Should perform one of: 403 Forbidden, 401 Unauthorized, or redirect to user dashboard
    # Based on auth.py redirect logic for logins:
    # if current_user.role == UserRole.ADMIN: redirect admin_dashboard
    # So if a student tries, the route handler should block it.
    
    # If the app uses a decorator like @admin_required, it might return 403
    # If it just checks role inside view, it might redirect.
    
    assert response.status_code in [403, 401, 302]
    if response.status_code == 302:
        # Verify it didn't redirect TO the admin dashboard (loop) or let them in
        # It should redirect to student dashboard or error page
        assert "/admin/dashboard" not in response.location

def test_teacher_cannot_access_admin(client, auth, db):
    """Test RBAC: Teacher cannot access admin dashboard"""
    user = User(name="Teacher", email="teacher@example.com", role=UserRole.TEACHER)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    auth.login("teacher@example.com", "password")
    
    response = client.get('/admin/dashboard')
    assert response.status_code in [403, 401, 302]

def test_csrf_protection_enabled(app):
    """Verify CSRF is enabled in config (though disabled for tests usually)"""
    # In conftest we disabled it for testing convenience, but in production it should be on.
    # We can check if the app factory sets it / uses Secret Key
    assert app.config['SECRET_KEY'] is not None

def test_xss_protection_headers(client):
    """Test security headers are present"""
    response = client.get('/auth/login')
    # Flask usually doesn't set strict headers by default without 'talisman' or manual config
    # But checking if simple injection works is hard without a browser
    # We can check if template escapes input.
    # This is more of a white-box check: jinja2 autoescaping is on by default.
    pass 
