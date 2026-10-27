"""
Standalone script to initialise the leave_management.db database.

Run:
    python create_database.py
"""

from database import init_db_standalone

if __name__ == '__main__':
    db_path = init_db_standalone()
    print(f'Database initialised successfully at: {db_path}')
