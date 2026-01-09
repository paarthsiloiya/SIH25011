
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Subject

app = create_app()
with app.app_context():
    subjects = Subject.query.all()
    print(f"Total Subjects: {len(subjects)}")
    for s in subjects:
        if 'Human' in s.name or 'Constitution' in s.name:
            print(f"ID: {s.id} | Code: {s.code} | Name: {s.name} | Branch: {s.branch}")
