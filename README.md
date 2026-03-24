# Park Guide App Backend

Django REST backend for the Park Guide App training module.

## Stack
- Django + Django REST Framework
- JWT authentication (SimpleJWT)
- PostgreSQL
- Custom user model (`accounts.CustomUser`)

## Current Features
- Course and module APIs
- Module completion tracking per user
- Course-level progress tracking per user
- Admin pages for courses, modules, module progress, and course progress

## Prerequisites
- Python 3.10+
- PostgreSQL running locally
- A PostgreSQL database/user matching current settings in [park_guide/settings.py](park_guide/settings.py)

Current DB config in settings:
- DB name: `pga_db`
- DB user: `admin`
- DB password: `ADMIN`
- Host: `localhost`
- Port: `5432`

## PostgreSQL Setup

### Install PostgreSQL

- Ubuntu/Debian:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

- Arch/Manjaro:

```bash
sudo pacman -S postgresql
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

- macOS (Homebrew):

```bash
brew install postgresql
brew services start postgresql
```

- Windows:
  - Install from https://www.postgresql.org/download/windows/
  - Use default port `5432`

### Create database and user

Open PostgreSQL shell:

For Linux:
```bash
sudo -u postgres psql
```

For Mac:
```bash
psql postgres
```
For Windows:
```bash
psql -U postgres
```

Run:

```sql
CREATE DATABASE pga_db;
CREATE USER admin WITH PASSWORD 'ADMIN';
GRANT ALL PRIVILEGES ON DATABASE pga_db TO admin;
GRANT ALL ON SCHEMA public TO admin;
```

Exit:

```sql
\q
```

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

2. Install core backend dependencies:

```bash
pip install django djangorestframework djangorestframework-simplejwt psycopg2-binary
pip install boto3
```

3. (Optional) Install additional packages from `requirements.txt` if you use it in your environment:

```bash
pip install -r requirements.txt
```

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

5. Create admin user (to access admin dashboard):

```bash
python manage.py createsuperuser
```

6. Start server:

```bash
python manage.py runserver
```

Server URL:
- `http://127.0.0.1:8000` (For android dev build using physical phone, please set this: adb reverse tcp:8000 tcp:8000)

## API Base Paths
- App API root: `/api/`
- Auth API root: `/api/accounts/`
- Notifications API root: `/api/notifications/`
- User progress API root: `/api/user-progress/`
- Secure files API root: `/api/secure-files/`

## Authentication Endpoints
- `POST /api/accounts/register/` – register user
- `POST /api/accounts/login/` – get JWT `access` and `refresh`

All course/progress endpoints require `Authorization: Bearer <access_token>`.

## Training Endpoints
- `GET /api/courses/` – list courses with nested modules
- `GET /api/modules/` – list modules
- `GET /api/progress/` – list module progress rows for logged-in user
- `GET /api/course-progress/` – list course progress rows for logged-in user
- `POST /api/complete-module/` – mark module completed and auto-update course progress

## Notification Endpoints
- `GET /api/notifications/items/` – list notifications for logged-in user
- `POST /api/notifications/items/{id}/mark-read/` – mark one notification as read
- `POST /api/notifications/items/mark-all-read/` – mark all as read
- `POST /api/notifications/items/clear-read/` – delete all read notifications for user

All notification endpoints require `Authorization: Bearer <access_token>`.

## Secure File Endpoints (Private S3)
- `GET /api/secure-files/files/` – list your uploaded files (admin sees all)
- `POST /api/secure-files/files/` – upload file with multipart field `file`
- `GET /api/secure-files/files/{id}/` – file metadata + temporary download URL
- `GET /api/secure-files/files/{id}/download-url/` – new temporary download URL
- `DELETE /api/secure-files/files/{id}/` – delete a file

All secure-file endpoints require `Authorization: Bearer <access_token>`.

## Private S3 Setup

Set environment variables before running server/commands:

```bash
export S3_ENABLED=true
export S3_BUCKET_NAME=parkguide-private-files
export S3_REGION_NAME=ap-southeast-1
export AWS_ACCESS_KEY_ID=<your-access-key>
export AWS_SECRET_ACCESS_KEY=<your-secret-key>

# Optional (for MinIO/LocalStack or S3-compatible providers)
export S3_ENDPOINT_URL=http://127.0.0.1:9000

# Optional (seconds for presigned URL)
export S3_PRESIGNED_URL_EXPIRY=300
```

Bootstrap bucket with private-access block:

```bash
python manage.py bootstrap_private_bucket
```

### Local Demo Setup (MinIO)

If you want to demo S3 locally without AWS, use MinIO:

```bash
sudo docker run -d --name parkguide-minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

If Docker says the container name already exists:

```bash
sudo docker start parkguide-minio
# or recreate cleanly:
sudo docker rm -f parkguide-minio
```

Use these environment values for MinIO:

```bash
export S3_ENABLED=true
export S3_BUCKET_NAME=parkguide-private-files
export S3_REGION_NAME=us-east-1
export S3_ENDPOINT_URL=http://127.0.0.1:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export S3_PRESIGNED_URL_EXPIRY=300
```

Then run:

```bash
python manage.py bootstrap_private_bucket
python manage.py runserver
adb reverse tcp:9000 tpc:9000
```

MinIO console URL:
- `http://127.0.0.1:9001`

### Quick Verification

1. Login to get JWT via `/api/accounts/login/`.
2. Upload a file to `/api/secure-files/files/` as multipart form field `file`.
3. Confirm `download_url` is returned and works for a short time.

### `POST /api/complete-module/` request body

```json
{
  "module_id": 1
}
```

### Example `course-progress` response row

```json
{
  "id": 1,
  "user": 2,
  "course": 1,
  "completed_modules": 2,
  "total_modules": 5,
  "progress": 0.4,
  "completed": false,
  "updated_at": "2026-03-16T12:00:00Z"
}
```

## Admin
Open Django admin:
- `http://127.0.0.1:8000/admin/`

Available sections under Courses:
- Course
- Module

Available sections under User Progress:
- Module progress
- Course progress
- Badge
- User badge

Available sections under Secure Files:
- Secure files (includes drag-and-drop upload area in admin list page)

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
- This backend currently uses hardcoded DB credentials in settings (fine for class/dev use, not production).
- The current `requirements.txt` appears to include many machine-specific packages; use the core dependency install command above as the minimum reliable setup.
- Secure files are stored in a private S3 bucket and accessed only with valid app auth + short-lived presigned URLs.
