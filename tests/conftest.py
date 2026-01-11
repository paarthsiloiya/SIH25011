import sys
import os
import pytest
from flask import Flask

# Add project root to path so tests can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db as _db, User, UserRole

@pytest.fixture(scope='session')
def app():
    """Create application for the tests."""
    # Force in-memory database configuration BEFORE creating app
    # to prevent create_app() from touching the real database file
    os.environ['DATABASE_URL'] = "sqlite:///:memory:"
       
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False  # Disable CSRF for easier testing
    })
    
    yield app

@pytest.fixture(scope='function')
def db(app):
    """
    Create a fresh database for each test.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def client(app, db):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's CLI commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth(client):
    """Auth helper for login"""
    class AuthActions:
        def login(self, email='test@example.com', password='password'):
            return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

        def logout(self):
            return client.get('/logout', follow_redirects=True)
            
    return AuthActions()
