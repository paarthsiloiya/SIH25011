import pytest
from app import create_app
from app.models import db, User, Subject, AssignedClass, TimetableSettings, TimetableEntry, UserRole, Branch
from app.timetable_generator import TimetableGenerator
from datetime import time

class TestTimetableEngine:
    
    @pytest.fixture
    def app(self):
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    @pytest.fixture
    def setup_data(self, app):
        """
        Setup complex scenario:
        - 2 Branches: AIML, CSE
        - 2 Semesters: 1 (Odd), 2 (Even), 3 (Odd)
        - 1 Shared Teacher (teaches across branches and semesters)
        """
        with app.app_context():
            settings = TimetableSettings(
                start_time=time(9, 0),
                end_time=time(12, 0), # 3 Hours
                periods=3,
                lunch_duration=0,
                working_days="Mon,Tue",
                max_class_duration=60,
                min_class_duration=40,
                active_semester_type='odd'
            )
            db.session.add(settings)

            teacher = User(name="Prof. Shared", email="shared@test.com", role=UserRole.TEACHER)
            teacher.set_password("password")
            db.session.add(teacher)

            # Subjects
            s1 = Subject(name="Math I", code="AIML-101", semester=1, branch="AIML")
            s2 = Subject(name="Math I CSE", code="CSE-101", semester=1, branch="CSE")
            s3 = Subject(name="Math III", code="AIML-301", semester=3, branch="AIML")
            s4 = Subject(name="Math II", code="AIML-201", semester=2, branch="AIML")
            db.session.add_all([s1, s2, s3, s4])
            db.session.flush()

            ac1 = AssignedClass(teacher_id=teacher.id, subject_id=s1.id)
            ac2 = AssignedClass(teacher_id=teacher.id, subject_id=s2.id)
            ac3 = AssignedClass(teacher_id=teacher.id, subject_id=s3.id)
            ac4 = AssignedClass(teacher_id=teacher.id, subject_id=s4.id)
            db.session.add_all([ac1, ac2, ac3, ac4])
            db.session.commit()
            return settings

    def test_config_validation(self, app, setup_data):
        with app.app_context():
            settings = TimetableSettings.query.first()
            
            # Invalid
            settings.min_class_duration = 70
            settings.max_class_duration = 60
            gen = TimetableGenerator(db, settings)
            assert gen.validate() == False
            
            # Valid
            settings.min_class_duration = 40
            gen = TimetableGenerator(db, settings)
            assert gen.validate() == True

    def test_timetable_generation_success(self, app, setup_data):
        with app.app_context():
            settings = TimetableSettings.query.first()
            gen = TimetableGenerator(db, settings)
            success = gen.generate_schedule()
            assert success == True
            assert len(gen.generated_entries) > 0

    def test_inter_branch_collision_avoidance(self, app, setup_data):
        """Test teacher collision avoidance across branches in same semester type"""
        with app.app_context():
            gen = TimetableGenerator(db, TimetableSettings.query.first())
            gen.generate_schedule()

            teacher = User.query.filter_by(email="shared@test.com").first()
            entries = TimetableEntry.query.join(AssignedClass).filter(AssignedClass.teacher_id == teacher.id).all()
            
            odd_entries = [e for e in entries if e.semester % 2 != 0]
            slots = [(e.day, e.period_number) for e in odd_entries]
            
            unique_slots = set(slots)
            assert len(slots) == len(unique_slots), f"Collision detected! {slots}"

    def test_lunch_break_logic(self, app):
        with app.app_context():
            settings = TimetableSettings(
                start_time=time(10, 0), end_time=time(13, 0), lunch_duration=60, periods=2, working_days="Mon"
            )
            db.session.add(settings)
            
            t = User(name="T", email="t@t.com", role=UserRole.TEACHER)
            t.set_password("p")
            s = Subject(name="T", code="T", semester=1)
            db.session.add_all([t, s])
            
            db.session.flush()
            ac = AssignedClass(teacher_id=t.id, subject_id=s.id)
            db.session.add(ac)
            db.session.commit()

            gen = TimetableGenerator(db, settings)
            gen.generate_schedule()
            
            entries = TimetableEntry.query.all()
            p1 = next((e for e in entries if e.period_number == 1), None)
            p2 = next((e for e in entries if e.period_number == 2), None)
            
            if p1 and p2:
                # Lunch after period 1 (2//2 = 1)
                # P1 start 10:00 -> End ? (Availability 120min / 2 = 60min) -> End 11:00
                assert p1.start_time == time(10, 0)
                # P2 start: 10:00 + 60 + 60(Lunch) = 12:00
                assert p2.start_time == time(12, 0)
