#!/usr/bin/env python3
"""
Subject Synchronization Script

This script forces a synchronization between branch_subjects.json and the database.
It will:
1. Add new subjects from JSON
2. Update existing subjects with new details
3. Remove subjects that are no longer in the JSON
"""

import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, seed_subjects

def sync():
    print("🔄 Starting subject synchronization...")
    app = create_app()
    with app.app_context():
        # seed_subjects now includes the sync/delete logic we just added
        seed_subjects()
        print("✅ Synchronization complete! Please check the dashboard.")

if __name__ == "__main__":
    sync()
