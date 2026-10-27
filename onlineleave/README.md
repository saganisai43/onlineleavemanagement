# Online Leave Management System

**VMR PRADEEP KUMAR INSTITUTION OF ENGINEERING AND TECHNOLOGY**  
*A Database-Driven Faculty Leave Application and HOD Approval Web Application (College MVP)*

---

## 1. Project Overview

The **Online Leave Management System** is a full-stack web application designed to digitize, streamline, and secure the faculty leave application and approval workflow. It replaces paper slips with an automated, role-based system.

### Key Features
- **Public Landing Page**: Dual portal entry with dedicated pathways for Faculty and HOD.
- **Faculty Portal**:
  - Secure registration and login.
  - Interactive dashboard showing real-time statistics (total allowance, approved days used, remaining balance, pending/approved/rejected counts).
  - Leave application with client-side and server-side validation (date conflict check, leave balance verification, automatic inclusive calendar day calculation).
  - Complete personal application history with status badges and HOD remarks.
- **HOD Portal**:
  - Administrative login (accounts created strictly via secure CLI to prevent unauthorized self-registration).
  - Management dashboard with status filtering (All, Pending, Approved, Rejected).
  - Transactional one-click approval and rejection with mandatory rejection remarks.
  - Real-time balance revalidation to prevent race conditions or balance overdrafts.
- **Application Security**:
  - Werkzeug password hashing (PBKDF2/SHA256).
  - Flask-WTF CSRF protection on all state-changing `POST` requests.
  - Parameterized SQLite queries everywhere (SQL injection immune).
  - Strict server-side role-based access control (RBAC).
  - `HttpOnly` and `SameSite=Lax` session cookies.

---

## 2. Technology Stack

- **Backend**: Python 3.11+ with Flask
- **Database**: SQLite3 via Python's built-in `sqlite3` module (`leave_management.db`)
- **Forms & Security**: Flask-WTF (CSRF protection), Werkzeug (password hashing)
- **Frontend**: HTML5, CSS3, JavaScript (ES6), and Jinja2 templating
- **Configuration**: `python-dotenv` for loading environment variables from `.env`
- **Testing**: `pytest` and Flask test client

---

## 3. Project Directory Structure

```text
onlineleave/
├── app.py                  # Core Flask app, routes, authentication, and CLI
├── database.py             # Schema, DB connection factory, and indexes
├── create_database.py      # Standalone database initialization script
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment configuration
├── .gitignore              # Ignores .venv, .db, .env, and caches
├── README.md               # Complete setup, execution, and testing guide
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout, header, footer, alerts, CSRF macro
│   ├── index.html          # Public landing page with Faculty & HOD portals
│   ├── login.html          # Unified login with portal context preservation
│   ├── register.html       # Public faculty registration form
│   ├── faculty_dashboard.html # Statistics cards & personal leave history
│   ├── apply_leave.html    # Leave form with live duration calculation
│   ├── hod_dashboard.html  # HOD review interface with filter tabs
│   └── error.html          # Custom error views (404, 403, 500)
├── static/
│   ├── css/
│   │   └── style.css       # Academic palette, responsive cards, status badges
│   └── js/
│       └── main.js         # Date calculation, character counter, alert timers
└── tests/
    └── test_app.py         # 20 automated tests verifying full lifecycle
```

---

## 4. Local Setup & Execution Guide (Windows)

Follow these step-by-step instructions in **Windows PowerShell** or **VS Code Terminal**.

### Step 1: Open the Project in VS Code
Open VS Code, press `Ctrl+O` or `File -> Open Folder...`, and select the `onlineleave` folder:
```powershell
cd c:\Users\venky\OneDrive\Desktop\onlineleave
code .
```

### Step 2: Create a Python Virtual Environment
```powershell
py -m venv .venv
```

### Step 3: Activate the Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the activate command again).*

### Step 4: Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
Copy `.env.example` to create your local `.env` file:
```powershell
Copy-Item .env.example .env
```
*(Optional) You can generate a random secret key for production:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
and paste it as `SECRET_KEY=...` inside your `.env` file.*

### Step 6: Initialize the Database
Run the standalone initialization script:
```powershell
python create_database.py
```
This generates `leave_management.db` with all tables, constraints, and indexes.

### Step 7: Create the HOD Account via CLI
HOD accounts cannot be registered publicly. Run the protected CLI command:
```powershell
python app.py --create-hod
```
You will be prompted to enter:
- **Full Name**: e.g., `Dr. K. V. Sharma (HOD CSE)`
- **Email**: e.g., `hod.cse@vmr.edu.in`
- **Password**: (Hidden securely as you type)
- **Confirm Password**

### Step 8: Start the Web Application
```powershell
python app.py
```
You will see output similar to:
```text
  Online Leave Management System
  VMR Pradeep Kumar Institution of Engineering and Technology
  http://127.0.0.1:5000
```

Open your browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 5. Demonstration Workflow

1. **Visit Landing Page** (`http://127.0.0.1:5000`):
   - Review the Faculty and HOD portal cards.
2. **Register a Faculty Member**:
   - Click **Continue as Faculty** -> click **Register as Faculty**.
   - Fill in full name (e.g. `Prof. Priya Ramesh`), email (`priya@vmr.edu.in`), and password (`password123`).
   - Notice the default 12-day leave allowance assigned automatically.
3. **Submit a Leave Application**:
   - From the Faculty Dashboard, click **Apply for Leave**.
   - Select leave type (`Casual Leave`), choose start and end dates.
   - Notice the dynamic calendar day calculator and character counter.
   - Submit the application. Your dashboard will show it under **Pending Requests**.
4. **Log In as HOD & Review**:
   - Log out from the faculty account.
   - Click **Continue as HOD** on the landing page and log in with your HOD credentials.
   - On the **HOD Management Dashboard**, locate the pending application.
   - Enter optional remarks and click **Approve** (or enter mandatory remarks and click **Reject**).
5. **Verify Dynamic Balance Deduction**:
   - Log out and log back in as the faculty member.
   - Observe that the **Approved Days Used** has increased, and **Remaining Balance** has decreased dynamically.
   - View HOD remarks in the application history table.

---

## 6. Running Automated Tests

A comprehensive test suite of 20 tests is included under `tests/test_app.py`, verifying authentication, role boundaries, balance arithmetic, concurrent approval safety, and CSRF protection.

Run the test suite with:
```powershell
python -m pytest -v
```

---

## 7. Database Reset Procedure

To reset the demo database to a completely clean state:
```powershell
Remove-Item leave_management.db
python create_database.py
python app.py --create-hod
```

---

## 8. Security & Production Deployment Considerations

- **Secret Key**: In production, set a cryptographically strong `SECRET_KEY` in `.env`.
- **HTTPS Enforcement**: In a production deployment with SSL/TLS, set `app.config['SESSION_COOKIE_SECURE'] = True`.
- **WSGI Server**: Do not run the built-in Flask server (`python app.py`) in production. Use a production WSGI server such as Waitress on Windows:
  ```powershell
  pip install waitress
  waitress-serve --port=5000 app:app
  ```
