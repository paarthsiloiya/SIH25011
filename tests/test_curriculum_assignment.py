import pytest
from app.models import db, User, Subject, AssignedClass, UserRole, Branch

def test_faculty_assignment_visibility(app, client, auth):
    """
    Test that assigning a teacher to a subject makes the teacher's name
    appear in the student's curriculum view.
    """
    with app.app_context():
        # 1. Setup Data
        # Create a Student
        student = User(
            name='Test Student',
            email='student@test.com',
            role=UserRole.STUDENT,
            branch=Branch.CSE,
            semester=1
        )
        student.set_password('password')
        db.session.add(student)
        
        # Create a Teacher
        teacher = User(
            name='Professor X',
            email='teacher@test.com',
            role=UserRole.TEACHER,
            branch=Branch.CSE
        )
        teacher.set_password('password')
        db.session.add(teacher)
        
        # Create a Subject for the student's branch/sem
        # Note: Code format must match seeder expectations if we were seeding, 
        # but here we manually create it.
        subject = Subject(
            name='Introduction to X-Men',
            code='CSE-101',
            branch='CSE',
            semester=1,
            credits=4
        )
        db.session.add(subject)
        db.session.commit() # Commit to get IDs
        
        # 2. Assign Teacher to Subject
        assignment = AssignedClass(
            teacher_id=teacher.id,
            subject_id=subject.id
        )
        db.session.add(assignment)
        db.session.commit()
        
        # Verify DB state
        assert AssignedClass.query.count() == 1
        assert AssignedClass.query.first().teacher.name == 'Professor X'

    # 3. Login as Student
    auth.login('student@test.com', 'password')
    
    # 4. Access Curriculum Page
    response = client.get('/curriculum')
    assert response.status_code == 200
    
    # 5. Check Output
    # The response data is HTML string. We check if the teacher's name is present.
    html = response.data.decode('utf-8')
    
    assert 'Introduction to X-Men' in html
    assert 'Professor X' in html, "Assigned faculty name not found in curriculum view"
