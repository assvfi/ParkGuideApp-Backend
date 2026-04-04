# Park Guide App Backend

Django REST backend for the Park Guide App training platform. This service handles authentication, training content, learner progress, badges, notifications, and secure file delivery.

## Stack
- Django + Django REST Framework
- JWT authentication (SimpleJWT)
- Neon PostgreSQL
- Custom user model (`accounts.CustomUser`)
- Firebase secure file storage

## Features
- Email-based registration and login
- Training courses and modules API
- Module completion and course progress tracking
- Badge progress and awarded badge endpoints
- In-app notifications with read/clear actions
- Secure file upload, download, and temporary signed URLs using Firebase Storage
- Django admin for courses, badges, notifications, users, and files

## Prerequisites
- Python 3.10+
- Project `.env` file from @MiyukiVigil
- Secrets files/credentials from @MiyukiVigil

Current configuration is environment-driven (see `park_guide/settings.py`):
- `DATABASE_URL` (Neon database URL)
- `DB_SSL_REQUIRE` (optional)
- `DB_CONN_MAX_AGE` (optional)
- `DB_CONN_HEALTH_CHECKS` (optional)

## Setup
1. Create and activate a virtual environment:

For Mac and Linux (Depnding on your terminal shell):
```bash
python -m venv venv
source venv/bin/activate
```

For Windows:
```bash
venv\Scripts\activate
```

2. Install backend dependencies:

```bash
pip install -r requirements.txt
```

3. Add required environment/secrets files provided by @MiyukiVigil:

- `.env`
- Firebase service account JSON (under `secrets/`)
- Any additional project secrets used by your environment

4. Run migrations:
For first time setup
```bash
python manage.py load_training_courses 
python manage.py makemigrations accounts courses
python manage.py migrate

```
After that when there's changes
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Load the bundled training data.

```bash
python manage.py load_training_courses
```

6. Create an admin user.

```bash
python manage.py createsuperuser
```

7. Verify Firebase Storage access.

```bash
python manage.py bootstrap_private_bucket
```

8. Optionally seed demo badges.

```bash
python manage.py seed_demo_badges
```

9. Start the server.

```bash
python manage.py runserver
```

Default local URL:
- `http://127.0.0.1:8000`

If you are testing from a physical Android device through a local dev build:

```bash
adb reverse tcp:8000 tcp:8000
```

## Neon Database
This backend now expects a Postgres connection string through `DATABASE_URL`, which makes Neon the easiest deployment target.

Example format:

```env
DATABASE_URL=postgresql://username:password@ep-example.ap-southeast-1.aws.neon.tech/dbname?sslmode=require
```

If the database is brand new, run:

## Secure File Endpoints (Firebase Storage)
- `GET /api/secure-files/files/` – list your uploaded files (admin sees all)
- `POST /api/secure-files/files/` – upload file with multipart field `file`
- `GET /api/secure-files/files/{id}/` – file metadata + temporary download URL
- `GET /api/secure-files/files/{id}/download-url/` – new temporary download URL
- `DELETE /api/secure-files/files/{id}/` – delete a file

## Firebase Storage
Secure file uploads are stored in Firebase Storage.

## Firebase Setup

- Requires Firebase service account JSON file, request from @MiyukiVigil
```bash
python manage.py bootstrap_private_bucket
```

If configured correctly, the command confirms that the bucket is accessible.

## API Overview
Base routes:
- `/api/`
- `/api/accounts/`
- `/api/notifications/`
- `/api/user-progress/`
- `/api/secure-files/`

Authentication:
- `POST /api/accounts/register/`
- `POST /api/accounts/login/`
- `POST /api/accounts/token/refresh/`

Training:
- `GET /api/courses/`
- `GET /api/modules/`
- `GET /api/progress/`
- `POST /api/progress/`
- `GET /api/course-progress/`
- `POST /api/course-progress/`
- `POST /api/complete-module/`

Badges:
- `GET /api/user-progress/badges/`
- `GET /api/user-progress/my-badges/`

Notifications:
- `GET /api/notifications/items/`
- `POST /api/notifications/items/{id}/mark-read/`
- `POST /api/notifications/items/mark-all-read/`
- `POST /api/notifications/items/clear-read/`

Secure files:
- `GET /api/secure-files/files/`
- `POST /api/secure-files/files/` with multipart field `file`
- `GET /api/secure-files/files/{id}/`
- `DELETE /api/secure-files/files/{id}/`
- `GET /api/secure-files/files/{id}/download-url/`
- `GET /api/secure-files/files/{id}/download/`

All API endpoints require `Authorization: Bearer <access_token>` unless noted otherwise.

## Admin
Admin URL:
- `/admin/`

Main admin areas include:
- Accounts
- Courses and modules
- User progress
- Badges and awarded badges
- Notifications
- Secure files

Notification send flow:
1. Create a notification in Django admin.
2. Select it in the changelist.
3. Run the action to send it to users.

## Useful Commands
```bash
python manage.py migrate
python manage.py load_training_courses
python manage.py seed_demo_badges
python manage.py bootstrap_private_bucket
python manage.py createsuperuser
python manage.py runserver
```

Available sections under Notifications:
- Notification
- User notification

Admin send flow:
1. Create a Notification in Django admin.
2. Select it from list view.
3. Run action: **Send selected notifications to all users**.

Demo badge setup command:
- `python manage.py seed_demo_badges` (creates selectable badges from current training courses/module data)

## Notes
- `ModuleProgress` and `CourseProgress` are the source of truth for learner progress.
- Admins can create badges and manage them with a pending workflow (`pending`, `granted`, `rejected`) based on each user's completed module count.
- Admin actions support syncing pending badges for eligible users, auto-approving pending badges, and auto-rejecting pending badges.
- Admins can also use a one-click action: **Sync pending then auto approve eligible users**.
- Notifications can be broadcast from admin to all regular app users in one action (excludes staff/admin accounts).
- New notifications created from admin are auto-broadcast immediately to all regular app users (no second step needed).
- Quiz data exists inside module content (`Module.quiz`) and now supports multiple quizzes per module.
- Training JSON can use either `quiz` (single object, backward compatible) or `quizzes` (array of quiz objects).
- Each quiz supports single-answer (`correctIndex`) and multi-answer (`correctIndexes`) with up to 3 correct choices.
- Posting to progress endpoints reuses and amends existing progress records for the same user/course or user/module instead of creating new IDs.
- Dependencies are maintained in `requirements.txt` and should stay project-focused only.
- Secure files are stored in Firebase private storage and accessed only with valid app auth + short-lived signed URLs.
