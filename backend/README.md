# RenderHive Backend

The RenderHive backend is built using Django and Django REST Framework.

## Tech Stack

- **Framework:** Django 6.x & Django REST Framework (DRF)
- **Dependency Management:** `uv`
- **Database:** PostgreSQL
- **Caching:** Redis

## Setup & Local Development

This project is configured to run entirely via Docker Compose from the root workspace directory.

### Prerequisites

- Docker & Docker Compose installed.

### Running the Services

1. Copy `.env.example` in the project root to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Build and start the services:
   ```bash
   docker compose up --build
   ```
3. Migrations, database health checks, and static files collection are handled automatically by the backend entrypoint script on container startup.

### Architecture Services

- **PostgreSQL (`postgres`)**: Exposes port `5432` for the database connection.
- **Redis (`redis`)**: Exposes port `6379` for caching/queuing.
- **API (`api`)**: Exposes port `8000` for the REST API.

### Code Style & Linting

We use Ruff for linting and formatting. You can run checks using:
```bash
uv run ruff check
```
