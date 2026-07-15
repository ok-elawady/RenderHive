# RenderHive Backend

The RenderHive backend is built using Django and Django REST Framework. It provides the core API for the render farm management system, serving both the web frontend (artists and administrators) and the worker nodes/DCC plugins.

## Tech Stack

- **Framework:** Django 6.x & Django REST Framework (DRF)
- **Authentication:** `django-allauth` (Headless configuration for Next.js integration)
- **Dependency Management:** `uv`
- **Database:** PostgreSQL
- **Caching:** Redis

## Architecture Overview

### Jobs API (`apps.jobs`)
Manages the hierarchy of rendering tasks:
- **Jobs**: High-level submissions.
- **Layers**: Sub-divisions of Jobs (e.g., specific render passes or steps).
- **Frames**: Granular execution units distributed to workers.
- **Dependencies**: Rules enforcing execution order (e.g., Frame-on-Frame or Layer-on-Layer).

### Authentication (`apps.users` / `allauth.headless`)
Authentication is split to serve two distinct clients:
1. **Frontend (Browser/Next.js)**: Utilizes `django-allauth` headless endpoints (at `/_allauth/browser/v1/auth/login`) which natively manages authentication via `X-Session-Token` headers.
2. **Workers & DCC Plugins**: Authenticate via a shared DRF API token passed as an `Authorization: Token <token>` header. 
   - A `farm_service` user and token are automatically generated on container startup by the `create_farm_token` command.
   - **How to get the token**: If randomly generated on first boot, the token will be printed to the Docker container logs.
   - **How to enforce a token**: You can enforce a deterministic, static token by providing `FARM_AGENT_TOKEN=your_secure_token_here` in your `.env` file. This is highly recommended so that you can easily deploy your worker configurations without checking the backend logs.

## OpenAPI Documentation

The backend dynamically generates OpenAPI documentation schemas for both DRF and Headless Auth:

- **Jobs API & Core Endpoints:**
  - Swagger UI: `/api/docs/`
  - Raw JSON Schema: `/api/schema/`
- **Authentication Endpoints:**
  - Auth Docs: `/_allauth/openapi.html`
  - Raw JSON Schema: `/_allauth/openapi.json`

## Setup & Local Development

This project is configured to run entirely via Docker Compose from the root workspace directory.

### Prerequisites

- Docker & Docker Compose installed.

### ⚠️ Critical Environment Variables

Before running the services, you **must** configure your `.env` file (copied from `.env.example`). The system automatically provisions several critical accounts on startup based on these variables:

1. **`DJANGO_SUPERUSER_PASSWORD`**: The default admin password. Change this from `admin` to prevent unauthorized access.
2. **`FARM_AGENT_TOKEN`**: Provide a secure, deterministic string (e.g. `FARM_AGENT_TOKEN=super_secret_token`) to authenticate worker nodes. If omitted, a random token is generated and printed to the logs.
3. **`SECRET_KEY`**: Change this before deploying to a shared/production environment to secure Django sessions and crypto.

### Running the Services

1. Copy `.env.example` in the project root to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Build and start the services:
   ```bash
   docker compose up --build
   ```
3. Migrations, database health checks, superuser creation (`DJANGO_SUPERUSER_USERNAME`), token creation, and static files collection are handled automatically by the backend entrypoint script (`entrypoint.sh`) on container startup.

### Architecture Services

- **PostgreSQL (`postgres`)**: Exposes port `5432` for the database connection.
- **Redis (`redis`)**: Exposes port `6379` for caching/queuing.
- **API (`api`)**: Exposes port `8000` for the REST API.

### Code Style & Linting

We use Ruff for linting and formatting. You can run checks using:
```bash
uv run ruff check
```
