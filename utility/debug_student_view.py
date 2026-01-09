
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Subject

app = create_app()
with app.app_context():
    # Simulate fetching for AIML Sem 1
    branch_code = 'AIML'
    semester = 1
    
    subjects = Subject.query.filter(
        Subject.semester == semester,
        db.or_(
            Subject.branch == branch_code,
            Subject.branch == 'COMMON'
        )
    ).all()
    
    print(f"--- Subjects for {branch_code} Sem {semester} ---")
    for s in subjects:
        print(f"Code: {s.code} | Name: {s.name} | Branch: {s.branch}")
