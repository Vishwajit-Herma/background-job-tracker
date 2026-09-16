# Local Installation & Setup

This guide walks you through running the full Background Job Tracker platform locally for development and evaluation.

---

## 📋 Prerequisites

Before starting, ensure you have the following installed on your machine:

- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- [Node.js 18+](https://nodejs.org/) & `npm` (for the Next.js frontend)
- [uv](https://github.com/astral-sh/uv) (optional, if running the backend outside Docker)

---

## 🚀 1. Backend Setup with Docker Compose

The simplest way to run all backend services (Django API, PostgreSQL, Redis, Celery Worker, Celery Beat, Mailpit) is using Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/Vishwajit-Herma/background-job-tracker.git
cd background-job-tracker

# 2. Copy environment configuration
cp .env.example .env

# 3. Start all backend containers in the background
docker compose up -d

# 4. Run database migrations inside the web container
docker compose exec web uv run python manage.py migrate

# 5. Create an initial superuser account
docker compose exec web uv run python manage.py createsuperuser
```

### Local Service Endpoints

Once Docker Compose starts:

| Service | Local URL | Description |
|---|---|---|
| **Django REST API** | [http://localhost:8000](http://localhost:8000) | Ingestion and management API |
| **OpenAPI / Swagger Docs** | [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/) | Interactive Swagger API documentation |
| **Django Admin** | [http://localhost:8000/admin/](http://localhost:8000/admin/) | Django staff administration portal |
| **Mailpit (Email Capture)** | [http://localhost:8025](http://localhost:8025) | Local inbox for invitation & alert emails |

---

## 💻 2. Frontend Setup (Next.js Dashboard)

The web dashboard is built with Next.js 15, TanStack Query, and Tailwind CSS.

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser. You can log in using the superuser account you created above.

---

## 🛠️ 3. Native Local Backend (Alternative without Docker Web Container)

If you prefer to run Django and Celery natively on your host machine while using Docker only for databases:

```bash
# 1. Start database, cache, and mailpit
docker compose up -d db redis mailpit

# 2. Install Python dependencies using uv
uv sync

# 3. Run migrations and start API
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000

# 4. (In separate terminals) Start Celery worker and beat
uv run celery -A config.celery app worker -l INFO
uv run celery -A config.celery beat -l INFO
```
