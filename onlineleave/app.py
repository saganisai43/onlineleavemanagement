"""
Online Leave Management System
Flask application for VMR Pradeep Kumar Institution of Engineering and Technology.

Routes, authentication, validation, leave workflows, and CLI HOD creation.
"""

import os
import sys
import argparse
import getpass
import sqlite3
import re
from datetime import datetime, date
import hashlib
import hmac
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash as _werkzeug_check_password_hash
from dotenv import load_dotenv

from database import get_db, close_db, init_db, DEFAULT_DATABASE


def check_password_hash(pwhash: str, password: str) -> bool:
    """Verify password against hash, supporting both pbkdf2 and modern scrypt algorithms."""
    if not pwhash or not password:
        return False
    if pwhash.startswith('scrypt:'):
        try:
            parts = pwhash.split('$', 2)
            if len(parts) == 3:
                method, salt, hashval = parts
                args = method[7:].split(':')
                if len(args) == 3:
                    n, r, p = map(int, args)
                    maxmem = 132 * n * r * p
                    computed = hashlib.scrypt(
                        password.encode('utf-8'),
                        salt=salt.encode('utf-8'),
                        n=n,
                        r=r,
                        p=p,
                        maxmem=maxmem,
                    ).hex()
                    return hmac.compare_digest(computed, hashval)
        except Exception:
            return False
    return _werkzeug_check_password_hash(pwhash, password)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  APPLICATION SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DATABASE'] = os.environ.get('DATABASE', DEFAULT_DATABASE)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

csrf = CSRFProtect(app)
app.teardown_appcontext(close_db)

DEFAULT_LEAVE_ALLOWANCE = 12
MAX_LEAVE_DAYS = 60
VALID_LEAVE_TYPES = ['Casual Leave', 'Sick Leave', 'Earned Leave']
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTHORIZATION DECORATORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def login_required(f):
    """Redirect to login if the user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def faculty_required(f):
    """Allow only authenticated users with the 'faculty' role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', portal='faculty'))
        if session.get('user_role') != 'faculty':
            flash('Access denied. This page is for faculty only.', 'error')
            if session.get('user_role') == 'hod':
                return redirect(url_for('hod_dashboard'))
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def hod_required(f):
    """Allow only authenticated users with the 'hod' role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', portal='hod'))
        if session.get('user_role') != 'hod':
            flash('Access denied. This page is for HOD only.', 'error')
            if session.get('user_role') == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PUBLIC & AUTHENTICATION ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route('/')
def index():
    """Public landing page with Faculty and HOD portal cards."""
    if 'user_id' in session:
        if session.get('user_role') == 'hod':
            return redirect(url_for('hod_dashboard'))
        return redirect(url_for('faculty_dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Log in an existing user (Faculty or HOD)."""
    if 'user_id' in session:
        if session.get('user_role') == 'hod':
            return redirect(url_for('hod_dashboard'))
        return redirect(url_for('faculty_dashboard'))

    portal = request.args.get('portal', '')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        portal = request.form.get('portal', '')

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html', portal=portal)

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', portal=portal)

        # Transparent scrypt migration if needed
        if not user['password_hash'].startswith('scrypt:'):
            try:
                new_hash = generate_password_hash(password)
                db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user['id']))
            except Exception:
                pass

        if portal in ('faculty', 'hod') and user['role'] != portal:
            other = 'HOD' if portal == 'faculty' else 'Faculty'
            flash(f'This account is not registered under this portal. Please use the {other} portal.', 'error')
            return render_template('login.html', portal=portal)

        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        session['user_role'] = user['role']

        flash(f'Welcome back, {user["full_name"]}!', 'success')
        if user['role'] == 'hod':
            return redirect(url_for('hod_dashboard'))
        return redirect(url_for('faculty_dashboard'))

    return render_template('login.html', portal=portal)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new Faculty account."""
    if 'user_id' in session:
        return redirect(url_for('faculty_dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        elif len(full_name) > 100:
            errors.append('Full name must be 100 characters or fewer.')

        if not email:
            errors.append('Email address is required.')
        elif not EMAIL_PATTERN.match(email):
            errors.append('Please enter a valid email address.')

        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        elif password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('register.html')

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('An account with this email address already exists.', 'error')
            return render_template('register.html')

        try:
            db.execute(
                """INSERT INTO users
                   (full_name, email, password_hash, role, leave_allowance)
                   VALUES (?, ?, ?, 'faculty', ?)""",
                (full_name, email, generate_password_hash(password), DEFAULT_LEAVE_ALLOWANCE),
            )
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login', portal='faculty'))
        except sqlite3.IntegrityError:
            flash('An account with this email address already exists.', 'error')
            return render_template('register.html')

    return render_template('register.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """Clear the session and redirect to the landing page."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FACULTY ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard():
    """Display the faculty member's leave statistics and history."""
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
    if not user:
        session.clear()
        flash('Account not found. Please log in again.', 'error')
        return redirect(url_for('login'))

    total_allowance = user['leave_allowance']
    approved_days = db.execute(
        'SELECT COALESCE(SUM(days), 0) AS total FROM leave_requests WHERE faculty_id = ? AND status = ?',
        (uid, 'Approved'),
    ).fetchone()['total']
    remaining_balance = total_allowance - approved_days

    pending_count = db.execute(
        'SELECT COUNT(*) AS cnt FROM leave_requests WHERE faculty_id = ? AND status = ?',
        (uid, 'Pending'),
    ).fetchone()['cnt']
    approved_count = db.execute(
        'SELECT COUNT(*) AS cnt FROM leave_requests WHERE faculty_id = ? AND status = ?',
        (uid, 'Approved'),
    ).fetchone()['cnt']
    rejected_count = db.execute(
        'SELECT COUNT(*) AS cnt FROM leave_requests WHERE faculty_id = ? AND status = ?',
        (uid, 'Rejected'),
    ).fetchone()['cnt']

    stats = {
        'total_allowance': total_allowance,
        'approved_days': approved_days,
        'remaining_balance': remaining_balance,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }

    leave_requests = db.execute(
        'SELECT * FROM leave_requests WHERE faculty_id = ? ORDER BY created_at DESC',
        (uid,),
    ).fetchall()

    return render_template('faculty_dashboard.html', stats=stats, leave_requests=leave_requests)


@app.route('/faculty/apply', methods=['GET', 'POST'])
@faculty_required
def apply_leave():
    """Submit a new leave application."""
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
    total_allowance = user['leave_allowance']
    approved_days = db.execute(
        'SELECT COALESCE(SUM(days), 0) AS total FROM leave_requests WHERE faculty_id = ? AND status = ?',
        (uid, 'Approved'),
    ).fetchone()['total']
    remaining_balance = total_allowance - approved_days

    if request.method == 'POST':
        leave_type = request.form.get('leave_type', '').strip()
        start_str = request.form.get('start_date', '').strip()
        end_str = request.form.get('end_date', '').strip()
        reason = request.form.get('reason', '').strip()

        errors = []
        start_date = None
        end_date = None
        days = 0

        if leave_type not in VALID_LEAVE_TYPES:
            errors.append('Please select a valid leave type.')

        if not start_str:
            errors.append('Start date is required.')
        else:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid start date format.')

        if not end_str:
            errors.append('End date is required.')
        else:
            try:
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid end date format.')

        if start_date and start_date < date.today():
            errors.append('Start date cannot be in the past.')

        if start_date and end_date and end_date < start_date:
            errors.append('End date cannot be before the start date.')

        if start_date and end_date and end_date >= start_date:
            days = (end_date - start_date).days + 1
            if days > MAX_LEAVE_DAYS:
                errors.append(f'A single leave request cannot exceed {MAX_LEAVE_DAYS} days.')

        if not reason:
            errors.append('Please provide a reason for your leave request.')
        elif len(reason) > 500:
            errors.append('Reason must be 500 characters or fewer.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template(
                'apply_leave.html',
                leave_types=VALID_LEAVE_TYPES,
                remaining_balance=remaining_balance,
            )

        try:
            db.execute('BEGIN IMMEDIATE')

            overlap = db.execute(
                """SELECT id FROM leave_requests
                   WHERE faculty_id = ? AND status IN ('Pending', 'Approved')
                   AND start_date <= ? AND end_date >= ?""",
                (uid, end_str, start_str),
            ).fetchone()

            if overlap:
                db.execute('ROLLBACK')
                flash('You already have a pending or approved request overlapping these dates.', 'error')
                return render_template(
                    'apply_leave.html',
                    leave_types=VALID_LEAVE_TYPES,
                    remaining_balance=remaining_balance,
                )

            pending_days = db.execute(
                'SELECT COALESCE(SUM(days), 0) AS total FROM leave_requests WHERE faculty_id = ? AND status = ?',
                (uid, 'Pending'),
            ).fetchone()['total']

            if (days + pending_days) > remaining_balance:
                db.execute('ROLLBACK')
                flash(
                    f'Insufficient leave balance. Remaining: {remaining_balance} days, Pending: {pending_days} days.',
                    'error',
                )
                return render_template(
                    'apply_leave.html',
                    leave_types=VALID_LEAVE_TYPES,
                    remaining_balance=remaining_balance,
                )

            db.execute(
                """INSERT INTO leave_requests
                   (faculty_id, start_date, end_date, days,
                    leave_type, reason, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'Pending')""",
                (uid, start_str, end_str, days, leave_type, reason),
            )
            db.execute('COMMIT')

            flash('Leave application submitted successfully!', 'success')
            return redirect(url_for('faculty_dashboard'))

        except sqlite3.Error:
            try:
                db.execute('ROLLBACK')
            except sqlite3.Error:
                pass
            flash('An error occurred. Please try again.', 'error')
            return render_template(
                'apply_leave.html',
                leave_types=VALID_LEAVE_TYPES,
                remaining_balance=remaining_balance,
            )

    return render_template(
        'apply_leave.html',
        leave_types=VALID_LEAVE_TYPES,
        remaining_balance=remaining_balance,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HOD ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route('/hod/dashboard')
@hod_required
def hod_dashboard():
    """Display all leave applications for HOD review."""
    db = get_db()

    faculty_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE role = 'faculty'"
    ).fetchone()['cnt']
    pending_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM leave_requests WHERE status = 'Pending'"
    ).fetchone()['cnt']
    approved_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM leave_requests WHERE status = 'Approved'"
    ).fetchone()['cnt']
    rejected_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM leave_requests WHERE status = 'Rejected'"
    ).fetchone()['cnt']

    stats = {
        'faculty_count': faculty_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }

    current_filter = request.args.get('status', 'all')

    if current_filter in ('Pending', 'Approved', 'Rejected'):
        applications = db.execute(
            """SELECT lr.*, u.full_name AS faculty_name, u.email AS faculty_email
               FROM leave_requests lr
               JOIN users u ON lr.faculty_id = u.id
               WHERE lr.status = ?
               ORDER BY lr.created_at DESC""",
            (current_filter,),
        ).fetchall()
    else:
        current_filter = 'all'
        applications = db.execute(
            """SELECT lr.*, u.full_name AS faculty_name, u.email AS faculty_email
               FROM leave_requests lr
               JOIN users u ON lr.faculty_id = u.id
               ORDER BY
                   CASE lr.status WHEN 'Pending' THEN 0 ELSE 1 END,
                   lr.created_at DESC"""
        ).fetchall()

    return render_template(
        'hod_dashboard.html',
        stats=stats,
        applications=applications,
        current_filter=current_filter,
    )


@app.route('/hod/review/<int:request_id>', methods=['POST'])
@hod_required
def review_request(request_id):
    """Approve or reject a pending leave request."""
    action = request.form.get('action', '')
    remarks = request.form.get('remarks', '').strip()

    if action not in ('approve', 'reject'):
        flash('Invalid action.', 'error')
        return redirect(url_for('hod_dashboard'))

    if action == 'reject' and not remarks:
        flash('Remarks are required when rejecting a request.', 'error')
        return redirect(url_for('hod_dashboard'))

    if len(remarks) > 500:
        flash('Remarks must be 500 characters or fewer.', 'error')
        return redirect(url_for('hod_dashboard'))

    db = get_db()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    try:
        db.execute('BEGIN IMMEDIATE')

        leave_req = db.execute(
            'SELECT * FROM leave_requests WHERE id = ? AND status = ?',
            (request_id, 'Pending'),
        ).fetchone()

        if not leave_req:
            db.execute('ROLLBACK')
            flash('This request has already been reviewed or does not exist.', 'warning')
            return redirect(url_for('hod_dashboard'))

        new_status = 'Approved' if action == 'approve' else 'Rejected'

        if new_status == 'Approved':
            faculty = db.execute(
                'SELECT * FROM users WHERE id = ?',
                (leave_req['faculty_id'],),
            ).fetchone()

            current_approved = db.execute(
                'SELECT COALESCE(SUM(days), 0) AS total FROM leave_requests WHERE faculty_id = ? AND status = ?',
                (leave_req['faculty_id'], 'Approved'),
            ).fetchone()['total']

            if (current_approved + leave_req['days']) > faculty['leave_allowance']:
                db.execute('ROLLBACK')
                flash(
                    f"Cannot approve: would exceed the faculty member's leave allowance ({faculty['leave_allowance']} days). Already approved: {current_approved} days.",
                    'error',
                )
                return redirect(url_for('hod_dashboard'))

            overlap = db.execute(
                """SELECT id FROM leave_requests
                   WHERE faculty_id = ? AND status = 'Approved' AND id != ?
                   AND start_date <= ? AND end_date >= ?""",
                (leave_req['faculty_id'], request_id, leave_req['end_date'], leave_req['start_date']),
            ).fetchone()

            if overlap:
                db.execute('ROLLBACK')
                flash('Cannot approve: overlapping approved leave exists.', 'error')
                return redirect(url_for('hod_dashboard'))

        db.execute(
            """UPDATE leave_requests
               SET status = ?, hod_remarks = ?, reviewed_at = ?
               WHERE id = ? AND status = 'Pending'""",
            (new_status, remarks, now, request_id),
        )

        changes = db.execute('SELECT changes()').fetchone()[0]
        if changes == 0:
            db.execute('ROLLBACK')
            flash('This request was already reviewed by another session.', 'warning')
            return redirect(url_for('hod_dashboard'))

        db.execute('COMMIT')

        flash(f'Leave request #{request_id} has been {new_status.lower()}.', 'success')

    except sqlite3.Error:
        try:
            db.execute('ROLLBACK')
        except sqlite3.Error:
            pass
        flash('A database error occurred. Please try again.', 'error')

    return redirect(url_for('hod_dashboard'))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ERROR HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message='The page you are looking for does not exist.'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', error_code=403, error_message='You do not have permission to access this page.'), 403


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, error_message='An internal server error occurred.'), 500


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_hod_account():
    with app.app_context():
        init_db()

        print('\n  ── Create HOD Account ─────────────────\n')

        full_name = input('  Full name : ').strip()
        if not full_name:
            print('\n  Error: Full name is required.')
            sys.exit(1)

        email = input('  Email     : ').strip().lower()
        if not email or not EMAIL_PATTERN.match(email):
            print('\n  Error: A valid email address is required.')
            sys.exit(1)

        password = getpass.getpass('  Password  : ')
        if len(password) < 8:
            print('\n  Error: Password must be at least 8 characters.')
            sys.exit(1)

        confirm = getpass.getpass('  Confirm   : ')
        if password != confirm:
            print('\n  Error: Passwords do not match.')
            sys.exit(1)

        db = get_db()
        existing = db.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()
        if existing:
            print(f'\n  Error: An account with email "{email}" already exists.')
            sys.exit(1)

        try:
            db.execute(
                """INSERT INTO users
                   (full_name, email, password_hash, role, leave_allowance)
                   VALUES (?, ?, ?, 'hod', 0)""",
                (full_name, email, generate_password_hash(password)),
            )
            print(f'\n  HOD account created successfully!')
            print(f'    Name  : {full_name}')
            print(f'    Email : {email}')
            print(f'    Role  : HOD\n')
        except sqlite3.IntegrityError:
            print(f'\n  Error: An account with email "{email}" already exists.')
            sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Online Leave Management System',
    )
    parser.add_argument(
        '--create-hod', action='store_true',
        help='Create an HOD account interactively',
    )
    args = parser.parse_args()

    if args.create_hod:
        create_hod_account()
    else:
        with app.app_context():
            init_db()

        debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
        print('\n  Online Leave Management System')
        print('  VMR Pradeep Kumar Institution of Engineering and Technology')
        print('  http://127.0.0.1:5000\n')
        app.run(debug=debug_mode, host='127.0.0.1', port=5000)
