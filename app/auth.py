from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, Branch
from datetime import datetime

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember-me') == 'on'
        
        # Validate input
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return redirect(url_for('auth.login'))
        
        # Find user in database
        user = User.query.filter_by(email=email.lower().strip()).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect to next page if specified, otherwise dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('views.dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    
    # GET request - show login form
    return render_template('Auth/login.html')

@auth.route('/signin', methods=['GET', 'POST'])
def signin():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        semester = request.form.get('semester')
        branch = request.form.get('branch')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')
        terms = request.form.get('terms')
        
        # Validation
        errors = []
        
        if not name or len(name.strip()) < 2:
            errors.append('Name must be at least 2 characters long.')
        
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        
        if not semester or not semester.isdigit() or int(semester) < 1 or int(semester) > 8:
            errors.append('Please select a valid semester (1-8).')
        
        if not branch or branch not in ['AIML', 'AIDS', 'CST', 'CSE']:
            errors.append('Please select a valid branch.')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not terms:
            errors.append('You must accept the terms and conditions.')
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email.lower().strip()).first()
        if existing_user:
            errors.append('An account with this email already exists.')
        
        # If there are errors, show them and return to form
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('auth.signin'))
        
        # Create new user
        try:
            new_user = User(
                name=name.strip(),
                email=email.lower().strip(),
                phone=phone.strip() if phone else None,
                semester=int(semester),
                branch=Branch(branch)
            )
            new_user.set_password(password)
            
            # Add to database
            db.session.add(new_user)
            db.session.commit()
            
            # Log in the new user
            login_user(new_user)
            flash(f'Account created successfully! Welcome, {new_user.name}!', 'success')
            return redirect(url_for('views.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'error')
            return redirect(url_for('auth.signin'))
    
    # GET request - show signin form
    return render_template('Auth/signin.html')

@auth.route('/logout')
@login_required
def logout():
    name = current_user.name
    logout_user()
    flash(f'You have been logged out successfully. Goodbye, {name}!', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/profile')
@login_required
def profile():
    """User profile page - placeholder for future implementation"""
    return render_template('Student/profile.html')  # You can create this template later