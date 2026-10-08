# 🎓 BunkWise — Smart Semester Attendance & Bunk Planner

> **Open Source Technologies (OST) — College Project**
> A complete student attendance management, semester calendar, attendance prediction, and bunk-planning system.

---

## 📸 Features

| Feature | Description |
|---|---|
| **Semester Setup** | Create semesters with start/end dates, min attendance %, and attendance policy |
| **Subject Management** | Per-subject min attendance, type (lecture/lab/tutorial), color, icon |
| **Weekly Timetable** | Define recurring schedule; supports session-based & period-based policies |
| **Auto Session Generation** | Generates every date-specific class session for the semester |
| **Interactive Calendar** | Month view with colored dots per session, holiday badges, click-to-mark |
| **Special Days** | Holidays, exams, college events, partial days — affects sessions correctly |
| **Attendance Marking** | Mark Present / Absent / Cancelled per session; edit any past record |
| **Attendance Calculation** | Mathematically correct using raw counts (not rounded percentages) |
| **Risk Indicators** | SAFE / CAUTION / CRITICAL per subject with configurable safety buffer |
| **Bunk Budget** | Max safe absences using floor((attended − threshold × conducted) / threshold) |
| **What-if Simulator** | Simulate any set of absences — real data stays unchanged |
| **Smart Bunk Optimizer** | Sessions / full day / date range — shows ranked risk and impact |
| **Event Planner** | Plan trips, medical appointments — see projected attendance impact |
| **Bridge Day Detector** | Finds isolated working days between holidays |
| **Recovery Planner** | Calculates consecutive sessions needed to recover to minimum % |
| **Analytics Charts** | 4 Matplotlib charts: bar, stacked, horizontal, trend (cumulative) |
| **Pandas Reports** | DataFrame summary table of attendance stats |
| **Auth** | Register / Login / Logout — each student sees only their own data |

---

## 🛠️ Technology Stack

| Technology | Role |
|---|---|
| **Django 6** | Backend framework — models, views, auth, business logic |
| **SQLite** | Default development database |
| **MySQL** | Optional production database (configure via `.env`) |
| **HTML5 / CSS3** | Semantic structure and dark glassmorphism theme |
| **Bootstrap 5** | Responsive grid, navbar, modals, badges |
| **JavaScript** | Calendar rendering, AJAX, interactive optimizer |
| **jQuery** | DOM helpers, datepicker |
| **Pandas** | Attendance analysis, grouping, DataFrame reports |
| **Matplotlib** | 4 server-side rendered charts embedded as base64 |
| **Git / GitHub** | Version control and portfolio hosting |

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- Git

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Krupal2057/bunkwise.git
cd bunkwise

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env and set your SECRET_KEY (already pre-generated for dev)

# 5. Apply database migrations
python manage.py migrate

# 6. Create a superuser (optional, for /admin panel)
python manage.py createsuperuser

# 7. Start the development server
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

---

## 🗄️ Database Configuration

### SQLite (default — no config needed)
```env
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
```

### MySQL (production)
```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=bunkwise
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
```
Then install mysqlclient: `pip install mysqlclient`

---

## 📐 Attendance Calculation Formulas

All calculations use raw integer counts internally. Percentages are only for display.

```
Attendance %     = (attended / conducted) × 100

Bunk Budget      = floor( (attended − threshold × conducted) / threshold )
                   where threshold = min_required / 100

Recovery needed  = ceil( (threshold × conducted − attended) / (1 − threshold) )

Projected after N absences:
                 = (attended / (conducted + N)) × 100
```

---

## 🏗️ Project Structure

```
bunkwise/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
│
├── bunkwise/               # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
└── attendance/             # Main application
    ├── models.py           # 10 database models
    ├── views.py            # All HTTP views
    ├── services.py         # All business logic (no logic in views!)
    ├── forms.py            # All Django forms
    ├── urls.py             # URL patterns
    ├── admin.py            # Django admin registration
    ├── context_processors.py
    ├── templatetags/
    │   └── bunkwise_tags.py  # Custom template filters
    ├── templates/          # All HTML templates
    └── static/             # CSS, JS, images
```

---

## 🧠 Key Design Decisions

1. **Services layer**: All attendance math lives in `services.py`. Views only handle HTTP.
2. **Raw counts as source of truth**: Never store percentages — always compute from integers.
3. **Configurable policy**: Session-based vs period-based (a 2h lab = 1 or 2 units).
4. **Simulation is safe**: What-if simulator never writes to `AttendanceRecord` or `ClassSession`.
5. **Explainable recommendations**: The optimizer always explains consequences, never just says "you can bunk N classes."

---

## 📊 Open Source Technologies Demonstrated

```
HTML/CSS/Bootstrap  →  Frontend structure & responsive design
JavaScript/jQuery   →  Calendar interactions, AJAX, dynamic UI
Django              →  MVC backend, ORM, auth, URL routing
SQLite/MySQL        →  Relational database with 10 normalized tables
Pandas              →  Attendance analysis, groupby, DataFrame reports
Matplotlib          →  4 charts: bar, stacked, horizontal, trend line
Git/GitHub          →  Version control, branching, clean commits
```

---

## 📝 License

MIT License — Open Source for academic and portfolio use.

---

*Built with ❤️ for the Open Source Technologies course.*
