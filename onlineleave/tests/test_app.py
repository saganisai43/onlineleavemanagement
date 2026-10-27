"""
Automated Test Suite for Online Leave Management System
VMR PRADEEP KUMAR INSTITUTION OF ENGINEERING AND TECHNOLOGY

Tests all 20 required scenarios using a temporary isolated SQLite test database.
"""

import os
import re
import tempfile
import sqlite3
from datetime import date, timedelta
import pytest
from werkzeug.security import generate_password_hash, check_password_hash

from app import app
from database import init_db_standalone, SCHEMA


@pytest.fixture
def client_and_db():
    """Create a temporary database and configured Flask test client."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    # Initialize schema
    init_db_standalone(db_path)

    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_client() as client:
        yield client, db_path

    if os.path.exists(db_path):
        os.remove(db_path)


# Helper functions
def create_user(db_path, full_name, email, password, role='faculty', allowance=12):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO users (full_name, email, password_hash, role, leave_allowance)
           VALUES (?, ?, ?, ?, ?)""",
        (full_name, email, generate_password_hash(password), role, allowance),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.close()
    return user_id


def create_leave_request(db_path, faculty_id, start_str, end_str, days, leave_type='Casual Leave', reason='Personal', status='Pending'):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO leave_requests (faculty_id, start_date, end_date, days, leave_type, reason, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (faculty_id, start_str, end_str, days, leave_type, reason, status),
    )
    conn.commit()
    req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return req_id


# ── Test Scenarios ───────────────────────────────────────────

def test_1_landing_page_renders_successfully(client_and_db):
    """1. Landing page renders successfully with both portal cards."""
    client, _ = client_and_db
    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Online Leave Management System' in html
    assert 'Faculty Portal' in html
    assert 'HOD Portal' in html
    assert 'VMR PRADEEP KUMAR INSTITUTION' in html


def test_2_faculty_registration_succeeds(client_and_db):
    """2. Faculty registration succeeds with valid data."""
    client, db_path = client_and_db
    res = client.post('/register', data={
        'full_name': 'Prof. John Doe',
        'email': 'john.doe@vmr.edu.in',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Registration successful' in html

    conn = sqlite3.connect(db_path)
    user = conn.execute("SELECT * FROM users WHERE email = 'john.doe@vmr.edu.in'").fetchone()
    conn.close()
    assert user is not None
    assert user[1] == 'Prof. John Doe'
    assert user[4] == 'faculty'  # role
    assert user[5] == 12         # default leave allowance


def test_3_duplicate_email_registration_rejected(client_and_db):
    """3. Registration using an existing email is rejected."""
    client, db_path = client_and_db
    create_user(db_path, 'Alice', 'alice@vmr.edu.in', 'password123')

    res = client.post('/register', data={
        'full_name': 'Alice Copy',
        'email': 'alice@vmr.edu.in',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert 'An account with this email address already exists' in res.get_data(as_text=True)


def test_4_passwords_stored_as_hashes(client_and_db):
    """4. Passwords are never stored in plaintext."""
    client, db_path = client_and_db
    raw_pass = 'SecretPass123'
    client.post('/register', data={
        'full_name': 'Bob Tester',
        'email': 'bob@vmr.edu.in',
        'password': raw_pass,
        'confirm_password': raw_pass,
    })

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT password_hash FROM users WHERE email = 'bob@vmr.edu.in'").fetchone()
    conn.close()
    assert row is not None
    stored_hash = row[0]
    assert stored_hash != raw_pass
    assert check_password_hash(stored_hash, raw_pass)


def test_5_valid_login_succeeds(client_and_db):
    """5. Valid login redirects to correct dashboard."""
    client, db_path = client_and_db
    create_user(db_path, 'Faculty Member', 'fac@vmr.edu.in', 'password123', role='faculty')

    res = client.post('/login', data={
        'email': 'fac@vmr.edu.in',
        'password': 'password123',
        'portal': 'faculty'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert 'Faculty Dashboard' in res.get_data(as_text=True)


def test_6_invalid_credentials_rejected(client_and_db):
    """6. Invalid login credentials show generic error message."""
    client, db_path = client_and_db
    create_user(db_path, 'User', 'user@vmr.edu.in', 'password123')

    res = client.post('/login', data={
        'email': 'user@vmr.edu.in',
        'password': 'wrongpassword',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert 'Invalid email or password' in res.get_data(as_text=True)


def test_7_faculty_cannot_access_hod_routes(client_and_db):
    """7. Faculty cannot access HOD routes."""
    client, db_path = client_and_db
    create_user(db_path, 'Faculty', 'fac@vmr.edu.in', 'password123', role='faculty')

    # Log in as faculty
    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})

    res = client.get('/hod/dashboard', follow_redirects=True)
    assert res.status_code == 200
    assert 'Access denied' in res.get_data(as_text=True)
    assert 'Faculty Dashboard' in res.get_data(as_text=True)


def test_8_hod_cannot_access_faculty_apply(client_and_db):
    """8. HOD cannot access Faculty-only application route."""
    client, db_path = client_and_db
    create_user(db_path, 'HOD User', 'hod@vmr.edu.in', 'password123', role='hod', allowance=0)

    # Log in as HOD
    client.post('/login', data={'email': 'hod@vmr.edu.in', 'password': 'password123'})

    res = client.get('/faculty/apply', follow_redirects=True)
    assert res.status_code == 200
    assert 'Access denied' in res.get_data(as_text=True)
    assert 'HOD Management Dashboard' in res.get_data(as_text=True)


def test_9_unauthenticated_cannot_access_protected_routes(client_and_db):
    """9. Unauthenticated users are redirected to login."""
    client, _ = client_and_db
    res1 = client.get('/faculty/dashboard', follow_redirects=True)
    assert 'Please log in to access this page' in res1.get_data(as_text=True)

    res2 = client.get('/hod/dashboard', follow_redirects=True)
    assert 'Please log in to access this page' in res2.get_data(as_text=True)


def test_9b_hod_routes_redirect_to_hod_login(client_and_db):
    """HOD-only routes send users to the HOD-specific login form."""
    client, _ = client_and_db
    res = client.get('/hod/dashboard', follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Please log in to access this page' in html
    assert 'HOD Portal Login' in html


def test_10_invalid_dates_and_leave_types_rejected(client_and_db):
    """10. Past dates, end before start, and invalid leave types are rejected."""
    client, db_path = client_and_db
    create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})

    # Past date
    past = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
    res = client.post('/faculty/apply', data={
        'leave_type': 'Casual Leave',
        'start_date': past,
        'end_date': past,
        'reason': 'Past test',
    }, follow_redirects=True)
    assert 'Start date cannot be in the past' in res.get_data(as_text=True)

    # End before start
    s = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
    e = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    res2 = client.post('/faculty/apply', data={
        'leave_type': 'Casual Leave',
        'start_date': s,
        'end_date': e,
        'reason': 'Invalid range',
    }, follow_redirects=True)
    assert 'End date cannot be before the start date' in res2.get_data(as_text=True)

    # Invalid leave type
    res3 = client.post('/faculty/apply', data={
        'leave_type': 'Vacation Leave',
        'start_date': s,
        'end_date': s,
        'reason': 'Invalid type test',
    }, follow_redirects=True)
    assert 'Please select a valid leave type' in res3.get_data(as_text=True)


def test_11_overlapping_requests_rejected(client_and_db):
    """11. Overlapping Pending or Approved requests are rejected."""
    client, db_path = client_and_db
    uid = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})

    d1 = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
    d2 = (date.today() + timedelta(days=15)).strftime('%Y-%m-%d')
    create_leave_request(db_path, uid, d1, d2, 6, status='Pending')

    # Overlapping submission: day 12 to 14
    overlap_s = (date.today() + timedelta(days=12)).strftime('%Y-%m-%d')
    overlap_e = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')

    res = client.post('/faculty/apply', data={
        'leave_type': 'Sick Leave',
        'start_date': overlap_s,
        'end_date': overlap_e,
        'reason': 'Overlapping leave',
    }, follow_redirects=True)
    assert 'overlapping these dates' in res.get_data(as_text=True)


def test_12_leave_allowance_limits_enforced(client_and_db):
    """12. Requests exceeding remaining allowance are rejected."""
    client, db_path = client_and_db
    uid = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty', allowance=5)
    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})

    # Request 6 days (more than allowance 5)
    s = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    e = (date.today() + timedelta(days=6)).strftime('%Y-%m-%d')

    res = client.post('/faculty/apply', data={
        'leave_type': 'Casual Leave',
        'start_date': s,
        'end_date': e,
        'reason': 'Excessive leave',
    }, follow_redirects=True)
    assert 'Insufficient leave balance' in res.get_data(as_text=True)


def test_13_faculty_can_submit_valid_leave(client_and_db):
    """13. Faculty can submit a valid leave request."""
    client, db_path = client_and_db
    create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})

    s = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    e = (date.today() + timedelta(days=4)).strftime('%Y-%m-%d')  # 3 days

    res = client.post('/faculty/apply', data={
        'leave_type': 'Casual Leave',
        'start_date': s,
        'end_date': e,
        'reason': 'Attending national workshop',
    }, follow_redirects=True)

    assert res.status_code == 200
    assert 'Leave application submitted successfully' in res.get_data(as_text=True)

    conn = sqlite3.connect(db_path)
    req = conn.execute("SELECT days, status FROM leave_requests WHERE reason LIKE '%workshop%'").fetchone()
    conn.close()
    assert req is not None
    assert req[0] == 3
    assert req[1] == 'Pending'


def test_14_hod_can_approve_pending_request(client_and_db):
    """14. HOD can approve a Pending request."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    create_user(db_path, 'HOD', 'hod@vmr.edu.in', 'password123', role='hod', allowance=0)

    s = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    e = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
    req_id = create_leave_request(db_path, f_id, s, e, 3, status='Pending')

    client.post('/login', data={'email': 'hod@vmr.edu.in', 'password': 'password123'})

    res = client.post(f'/hod/review/{req_id}', data={
        'action': 'approve',
        'remarks': 'Approved, please arrange substitute teacher.',
    }, follow_redirects=True)

    assert res.status_code == 200
    assert 'has been approved' in res.get_data(as_text=True)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, hod_remarks FROM leave_requests WHERE id = ?", (req_id,)).fetchone()
    conn.close()
    assert row[0] == 'Approved'
    assert 'substitute' in row[1]


def test_15_hod_can_reject_with_remarks(client_and_db):
    """15. HOD can reject a Pending request with mandatory remarks."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    create_user(db_path, 'HOD', 'hod@vmr.edu.in', 'password123', role='hod', allowance=0)

    s = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    e = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
    req_id = create_leave_request(db_path, f_id, s, e, 2, status='Pending')

    client.post('/login', data={'email': 'hod@vmr.edu.in', 'password': 'password123'})

    # Reject without remarks should fail
    res_no_remarks = client.post(f'/hod/review/{req_id}', data={
        'action': 'reject',
        'remarks': '',
    }, follow_redirects=True)
    assert 'Remarks are required when rejecting' in res_no_remarks.get_data(as_text=True)

    # Reject with remarks should succeed
    res_ok = client.post(f'/hod/review/{req_id}', data={
        'action': 'reject',
        'remarks': 'Department inspection scheduled on those days.',
    }, follow_redirects=True)
    assert 'has been rejected' in res_ok.get_data(as_text=True)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, hod_remarks FROM leave_requests WHERE id = ?", (req_id,)).fetchone()
    conn.close()
    assert row[0] == 'Rejected'
    assert 'inspection' in row[1]


def test_16_reviewed_requests_cannot_be_reviewed_again(client_and_db):
    """16. Approved or Rejected requests cannot be reviewed again."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty')
    create_user(db_path, 'HOD', 'hod@vmr.edu.in', 'password123', role='hod', allowance=0)

    s = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    req_id = create_leave_request(db_path, f_id, s, s, 1, status='Approved')

    client.post('/login', data={'email': 'hod@vmr.edu.in', 'password': 'password123'})

    res = client.post(f'/hod/review/{req_id}', data={
        'action': 'reject',
        'remarks': 'Trying to re-review',
    }, follow_redirects=True)

    assert 'already been reviewed' in res.get_data(as_text=True)


def test_17_leave_balance_calculation_accuracy(client_and_db):
    """17. Remaining leave = allowance - approved days."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty', allowance=12)

    # 3 approved days, 4 pending days, 2 rejected days
    create_leave_request(db_path, f_id, '2026-11-01', '2026-11-03', 3, status='Approved')
    create_leave_request(db_path, f_id, '2026-11-10', '2026-11-13', 4, status='Pending')
    create_leave_request(db_path, f_id, '2026-11-20', '2026-11-21', 2, status='Rejected')

    client.post('/login', data={'email': 'fac@vmr.edu.in', 'password': 'password123'})
    res = client.get('/faculty/dashboard')
    html = res.get_data(as_text=True)

    # Remaining balance should be 12 - 3 = 9
    assert '9 <span class="stat-unit">days</span>' in html
    assert '3 <span class="stat-unit">days</span>' in html  # approved days used


def test_18_failed_approvals_do_not_partially_modify_db(client_and_db):
    """18. If approval exceeds allowance, transaction rolls back cleanly."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Fac', 'fac@vmr.edu.in', 'password123', role='faculty', allowance=4)
    create_user(db_path, 'HOD', 'hod@vmr.edu.in', 'password123', role='hod', allowance=0)

    # Already approved 3 days
    create_leave_request(db_path, f_id, '2026-11-01', '2026-11-03', 3, status='Approved')
    # Another pending request of 2 days (3 + 2 = 5 > allowance of 4)
    req_id = create_leave_request(db_path, f_id, '2026-11-10', '2026-11-11', 2, status='Pending')

    client.post('/login', data={'email': 'hod@vmr.edu.in', 'password': 'password123'})
    res = client.post(f'/hod/review/{req_id}', data={'action': 'approve', 'remarks': 'Ok'}, follow_redirects=True)

    assert 'would exceed the faculty member' in res.get_data(as_text=True)

    # Verify request status remained Pending
    conn = sqlite3.connect(db_path)
    status = conn.execute("SELECT status FROM leave_requests WHERE id = ?", (req_id,)).fetchone()[0]
    conn.close()
    assert status == 'Pending'


def test_19_data_persists_across_app_restart(client_and_db):
    """19. Database persists records when connection restarts."""
    client, db_path = client_and_db
    f_id = create_user(db_path, 'Dr. Smith', 'smith@vmr.edu.in', 'password123', role='faculty')
    req_id = create_leave_request(db_path, f_id, '2026-12-01', '2026-12-02', 2, status='Approved')

    # Close and reopen new connection to verify disk persistence
    conn = sqlite3.connect(db_path)
    user = conn.execute("SELECT full_name FROM users WHERE id = ?", (f_id,)).fetchone()
    req = conn.execute("SELECT status FROM leave_requests WHERE id = ?", (req_id,)).fetchone()
    conn.close()

    assert user[0] == 'Dr. Smith'
    assert req[0] == 'Approved'


def test_20_csrf_protection_enabled_and_enforced():
    """20. CSRF protection rejects state-changing POST requests without token."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    init_db_standalone(db_path)

    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF enforcement
    app.config['SECRET_KEY'] = 'csrf-secret-key'

    with app.test_client() as client:
        # POST without CSRF token
        res = client.post('/register', data={
            'full_name': 'Hacker',
            'email': 'hack@vmr.edu.in',
            'password': 'password123',
            'confirm_password': 'password123',
        })
        # Flask-WTF responds with 400 Bad Request on missing CSRF token
        assert res.status_code == 400

    if os.path.exists(db_path):
        os.remove(db_path)
