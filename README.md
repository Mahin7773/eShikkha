# eShikkha – Learning Management System

A course marketplace and learning platform built with Django for an academic software engineering project, inspired by Udemy. Instructors publish and sell courses, students buy and complete them, and administrators moderate the platform.

> **All payments are simulated.** No payment provider is integrated, no card details are collected and no money moves. Instructor earnings are reporting figures only.

## Screenshots

![eShikkha home page](docs/screenshots/01-home.png)

### Student workflow: discover → buy → learn → certify

<table>
<tr><td width="50%" valign="top"><img src="docs/screenshots/02-catalog.png" alt="Catalogue with search, topic chips and filters"><br><sub><b>1.</b> Catalogue with search, topic chips and filters</sub></td><td width="50%" valign="top"><img src="docs/screenshots/03-course-detail.png" alt="Course page: objectives, curriculum, instructor and reviews"><br><sub><b>2.</b> Course page: objectives, curriculum, instructor and reviews</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/04-cart.png" alt="Cart, with prices confirmed on the server"><br><sub><b>3.</b> Cart, with prices confirmed on the server</sub></td><td width="50%" valign="top"><img src="docs/screenshots/05-checkout.png" alt="Order review before payment"><br><sub><b>4.</b> Order review before payment</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/06-payment-gateway.png" alt="Simulated payment gateway: approve, decline or cancel"><br><sub><b>5.</b> Simulated payment gateway: approve, decline or cancel</sub></td><td width="50%" valign="top"><img src="docs/screenshots/07-payment-success.png" alt="Payment approved; courses unlocked"><br><sub><b>6.</b> Payment approved; courses unlocked</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/09-learning-dashboard.png" alt="Learning dashboard with resume card and progress"><br><sub><b>7.</b> Learning dashboard with resume card and progress</sub></td><td width="50%" valign="top"><img src="docs/screenshots/10-course-player.png" alt="Course player: lesson list, video, materials and progress"><br><sub><b>8.</b> Course player: lesson list, video, materials and progress</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/11-quiz-intro.png" alt="Quiz rules: pass mark, time limit and attempts"><br><sub><b>9.</b> Quiz rules: pass mark, time limit and attempts</sub></td><td width="50%" valign="top"><img src="docs/screenshots/12-quiz-attempt.png" alt="Timed quiz attempt"><br><sub><b>10.</b> Timed quiz attempt</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/13-quiz-result.png" alt="Graded result with correct answers and explanations"><br><sub><b>11.</b> Graded result with correct answers and explanations</sub></td><td width="50%" valign="top"><img src="docs/screenshots/14-certificates.png" alt="Certificates ready to download as PDF"><br><sub><b>12.</b> Certificates ready to download as PDF</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/15-certificate-verification.png" alt="Public certificate verification page"><br><sub><b>13.</b> Public certificate verification page</sub></td><td width="50%" valign="top"><img src="docs/screenshots/08-purchase-history.png" alt="Purchase history"><br><sub><b>14.</b> Purchase history</sub></td></tr>
</table>

<p align="center"><img src="docs/screenshots/10b-course-player-mobile.png" alt="Course player on mobile" width="300"><br><sub>The course player on a phone</sub></p>

### Instructor workflow: design → submit → teach → track

<table>
<tr><td width="50%" valign="top"><img src="docs/screenshots/20-studio-dashboard.png" alt="Studio dashboard: courses, students and earnings"><br><sub><b>1.</b> Studio dashboard: courses, students and earnings</sub></td><td width="50%" valign="top"><img src="docs/screenshots/21-create-course.png" alt="Create a course: details, pricing and completion rules"><br><sub><b>2.</b> Create a course: details, pricing and completion rules</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/22-curriculum-builder.png" alt="Curriculum builder: sections, lessons and ordering"><br><sub><b>3.</b> Curriculum builder: sections, lessons and ordering</sub></td><td width="50%" valign="top"><img src="docs/screenshots/23-lesson-editor.png" alt="Lesson editor with video and lecture materials"><br><sub><b>4.</b> Lesson editor with video and lecture materials</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/24-quiz-builder.png" alt="Quiz builder"><br><sub><b>5.</b> Quiz builder</sub></td><td width="50%" valign="top"><img src="docs/screenshots/25-question-editor.png" alt="Question editor: multiple choice and true/false"><br><sub><b>6.</b> Question editor: multiple choice and true/false</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/26-moderation-feedback.png" alt="Course status, readiness checklist and admin feedback"><br><sub><b>7.</b> Course status, readiness checklist and admin feedback</sub></td><td width="50%" valign="top"><img src="docs/screenshots/27-student-progress.png" alt="Enrolled students' progress and quiz scores"><br><sub><b>8.</b> Enrolled students' progress and quiz scores</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/28-quiz-analytics.png" alt="Quiz analytics: pass rate and per-question accuracy"><br><sub><b>9.</b> Quiz analytics: pass rate and per-question accuracy</sub></td><td width="50%" valign="top"><img src="docs/screenshots/29-earnings.png" alt="Estimated earnings breakdown"><br><sub><b>10.</b> Estimated earnings breakdown</sub></td></tr>
</table>

### Administrator workflow: review → moderate → manage → audit

<table>
<tr><td width="50%" valign="top"><img src="docs/screenshots/30-admin-dashboard.png" alt="Admin dashboard with review, application and report queues"><br><sub><b>1.</b> Admin dashboard with review, application and report queues</sub></td><td width="50%" valign="top"><img src="docs/screenshots/31-review-queue.png" alt="Courses waiting for review"><br><sub><b>2.</b> Courses waiting for review</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/32-course-moderation.png" alt="Moderation view: content, quizzes, instructor and decision"><br><sub><b>3.</b> Moderation view: content, quizzes, instructor and decision</sub></td><td width="50%" valign="top"><img src="docs/screenshots/37-reports.png" alt="Reported content"><br><sub><b>4.</b> Reported content</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/33-user-management.png" alt="User management: search, filter, suspend"><br><sub><b>5.</b> User management: search, filter, suspend</sub></td><td width="50%" valign="top"><img src="docs/screenshots/34-user-detail.png" alt="User detail: role, suspension and granting access"><br><sub><b>6.</b> User detail: role, suspension and granting access</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/35-transactions.png" alt="Payment transactions"><br><sub><b>7.</b> Payment transactions</sub></td><td width="50%" valign="top"><img src="docs/screenshots/36-platform-analytics.png" alt="Platform analytics"><br><sub><b>8.</b> Platform analytics</sub></td></tr>
<tr><td width="50%" valign="top"><img src="docs/screenshots/38-settings.png" alt="Platform policies and certificate template"><br><sub><b>9.</b> Platform policies and certificate template</sub></td><td width="50%" valign="top"><img src="docs/screenshots/39-audit-log.png" alt="Audit log of admin actions"><br><sub><b>10.</b> Audit log of admin actions</sub></td></tr>
</table>

## Quick start

Requirements: Python 3.12 or later. It was developed with Python 3.14 and Django 6.0.8.

```bash
# 1. Create and activate a virtual environment (or use an existing conda env)
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database
python manage.py migrate

# 4. (Recommended) Load demo data: users, 12 courses, purchases, progress, reviews
python manage.py seed_demo

# 5. Run
python manage.py runserver
```

Open http://127.0.0.1:8000.

| Demo account | Username | Password | Lands on |
|---|---|---|---|
| Student | `student` | `Demo@12345` | `/learn/`: learning dashboard |
| Instructor | `instructor` | `Demo@12345` | `/teach/`: instructor studio |
| Administrator | `admin` | `Demo@12345` | `/manage/`: admin panel |

You can log in with either the username or the email address (for example `student@eshikkha.local`). The admin account is also a Django superuser, so it can open the secondary `/django-admin/` back office.

To start again from an empty database, run `python manage.py flush`, then `python manage.py seed_demo`.

For a database without demo data, run `python manage.py createsuperuser`. Superusers automatically get the administrator role.

### Running the tests

```bash
python manage.py test
```

The 42 tests cover:
- payment idempotency and price tampering
- declined and cancelled payments
- refunds
- lesson access control
- quiz attempt limits, deadlines and answer leakage
- the progress formula
- certificate uniqueness and verification
- the moderation workflow
- instructor ownership checks
- suspensions
- instructor applications

## Optional technologies and setup notes

| Need | Default | How to change |
|---|---|---|
| Database | SQLite (`db.sqlite3`) | Install `psycopg[binary]` and set `DATABASES` in `eShikkha/settings.py` to PostgreSQL. The models use no SQLite-specific features. Row locks (`select_for_update`) and partial unique constraints are fully enforced on PostgreSQL. |
| Media storage | Local `media/` folder | Uploaded videos and resources are served through access-checked views. For production, use object storage (for example `django-storages`) and an X-Accel/X-Sendfile setup. |
| Email | Console backend (printed in the terminal) | Set `EMAIL_BACKEND` and SMTP settings. |
| QR codes on certificates | `qrcode` package | If it isn't installed, certificates print the verification URL without a QR code. |
| Fonts | Inter from Google Fonts | Falls back to system fonts offline. |
| Sample lesson videos | Public CC0 clips from MDN, streamed over the internet | Upload your own video files in the studio, or paste YouTube/Vimeo links. |

Production settings are read from environment variables: `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0`. Also set `ALLOWED_HOSTS` and run `collectstatic`.

## Architecture

```
eShikkha/        project settings and root URLs
core/            platform settings, audit log, reports, announcements, RBAC decorators,
                 template tags (ui), protected file serving, seed_demo command
accounts/        custom User (role, profile, suspension), instructor applications, auth views
courses/         catalogue models, marketplace search (selectors.py), moderation + review rules (services.py)
learning/        enrolments, progress, course player, certificates (PDF via ReportLab), verification
assessments/     quizzes, attempts, server-side grading and attempt rules
commerce/        cart, orders, simulated payment gateway, instructor earnings, refunds
notifications/   in-app notifications
studio/          instructor workspace (views/forms only; uses the domain services)
adminpanel/      moderation-focused admin console (views/forms only)
templates/       Django templates (base layout, partials, one folder per app)
static/          design-system CSS and a small progressive-enhancement JS file
docs/            database design and ER diagram
```

The business logic lives in each app's `services.py` (writes) and `selectors.py` (complex reads). Views stay thin: they parse input, call a service and render. This makes the rules easy to test without HTTP. For example, `commerce.services.process_payment` and `learning.services.recalculate_progress` are tested directly.

## Feature walkthrough

### Student
- Browse the marketplace: search by title, description, instructor, tag or category; filter by category, level, price and rating; sort by popularity, rating, newest or price; results are paginated.
- See course pages with objectives, requirements, curriculum, free preview lessons, the instructor profile, a rating breakdown and reviews.
- Add courses to a cart or use **Buy now**, then go through checkout and the **sandbox gateway**, where you choose *approve*, *decline* or *cancel*.
- Use the learning dashboard: resume where you left off, see in-progress and completed courses, quiz activity and statistics.
- Use the course player:
  - uploaded or embedded video
  - a sidebar with completed, current and locked states
  - Overview, Materials, Quizzes and Progress tabs
  - previous/next navigation and **Mark as complete**
- Take quizzes with an optional server-enforced time limit and attempt limits, then see results and explanations according to the instructor's settings.
- Earn certificates: a downloadable PDF with a QR code and a public verification page at `/verify/<id>/`.
- Leave reviews (after the configured minimum progress), report content, view purchase history, and edit your profile and password.

### Instructor (`/teach/`)
- Create courses with details, media, pricing (discounts with optional end dates) and completion rules: sequential unlocking, required quizzes and certificates.
- Build the curriculum: sections and lessons, reordering, video upload or URL, article lessons, free previews, required or optional lessons, a "complete when quiz passed" rule, and lecture materials (PDF, slides, documents, files or links).
- Build quizzes: single- and multiple-answer multiple choice, true/false, points, explanations, pass mark, time limit, attempt limit, shuffling and result visibility.
- Use the moderation workflow: a readiness checklist, submission for review, admin feedback with a history timeline, and archive/restore. Editing is locked while a course is under review.
- See students (progress and best quiz scores), per-question correct rates, reviews and a simulated earnings breakdown.

### Administrator (`/manage/`)
- Use the dashboard: platform statistics and queues for courses awaiting review, instructor applications and open reports.
- Moderate courses: a full review view (description, curriculum, resources, quiz answer keys, pricing, instructor) with approve, request changes, reject, unpublish and archive. A reason is required for everything except approval.
- Manage users: search and filter, suspend or reactivate with a reason, change roles, and grant authorised enrolments.
- Moderate reviews (hide or restore with a reason) and work through the reports queue.
- See simulated transactions and orders, with a refund that revokes access and reverses earnings.
- Manage categories, tags and announcements, and edit platform settings, including policies and the certificate template.
- Use the analytics page and the append-only audit log.
- Administrators **cannot impersonate** users. No sign-in-as feature exists; accounts are inspected through read-only views.

## Security and integrity rules

- **Prices are server-side.** Orders read prices from the database, and the browser only sends course IDs and an outcome keyword. A test checks that a posted `price=0.01` is ignored.
- **Payments are idempotent.** The order row is locked, an already-paid order returns its original transaction, and a database constraint allows only one successful transaction per order.
- **Access is checked server-side.** Lesson pages, video streams and resource downloads all check for an active enrolment, ownership or the admin role. Uploaded videos and resources are not publicly served from `/media/`.
- **Progress and certificates are derived on the server** from completion and attempt rows; there is no endpoint that accepts a progress value.
- **Quiz answers never reach the browser before they're allowed.** The quiz page contains no correctness data, and submitted option IDs are validated against each question.
- **Role-based access control** is applied to every view, and instructors can only load their own courses (other courses return 404).
- **Standard Django protections** are on: CSRF on every form, password validators, and safe redirects for `next` URLs. Suspended accounts are signed out on their next request.

See [docs/DATABASE.md](docs/DATABASE.md) for the ER diagram and an explanation of the relationships.
