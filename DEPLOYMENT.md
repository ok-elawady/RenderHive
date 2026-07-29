# RenderHive — Deployment Guide

This guide walks through deploying RenderHive for a local area network (LAN) environment such as a studio lab or classroom. By the end, the server will be running, all client machines will be able to reach the dashboard through a browser, and Maya artists will be able to submit render jobs.

---

## Prerequisites

### Server Machine
| Requirement | Notes |
|---|---|
| Docker Desktop (or Docker Engine) | [docker.com/get-started](https://www.docker.com/get-started) |
| Docker Compose v2 | Bundled with Docker Desktop |
| Git | To clone the repository |
| A static LAN IP | e.g. `192.168.100.5` — set this in your router or OS network settings |

### Client / Worker Machines
| Requirement | Notes |
|---|---|
| Windows 10/11 | Worker installer is Windows-only |
| Autodesk Maya 2022+ | For job submission via the Maya plugin. Maya 2022–2024 uses PySide2; Maya 2025+ uses PySide6. The plugin handles both automatically. |
| Admin rights | Required by the worker installer to modify the hosts file |

---

## Part 1 — Server Setup

### 1.1 Clone the Repository

```bash
git clone https://github.com/ok-elawady/RenderHive.git RenderHive
cd RenderHive
```

### 1.2 Create the Environment File

Copy the example file and open it for editing:

```bash
cp .env.example .env
```

Edit `.env` and fill in the values below. Everything not listed can stay at its default.

```env
# --- SECURITY ---
# Generate a strong random key: python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=your-strong-secret-key-here

# --- DATABASE ---
POSTGRES_PASSWORD=change-me-to-a-strong-password
DATABASE_URL=postgres://postgres:change-me-to-a-strong-password@postgres:5432/renderhive

# --- NETWORK ---
# Add the server's LAN IP and both domain names used by the worker installer.
ALLOWED_HOSTS=192.168.100.5,localhost,127.0.0.1,renderhive.local,server.renderhive.local

# CORS and CSRF must allow requests coming from the frontend domain.
CORS_ALLOWED_ORIGINS=http://renderhive.local
CSRF_TRUSTED_ORIGINS=http://renderhive.local

# --- FRONTEND ---
# The URL the browser uses to reach the backend API.
# Use the domain name so it works on any client that has the worker installer.
NEXT_PUBLIC_API_URL=http://server.renderhive.local

# --- ADMIN ACCOUNT ---
# The superuser created automatically on first boot.
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@renderhive.local
DJANGO_SUPERUSER_PASSWORD=change-me-to-a-strong-password
```

> **Note:** `.env` is gitignored and will never be committed. Keep it safe — it contains secrets.

### 1.3 Start the Stack

```bash
docker compose --profile frontend up --build -d
```

This starts four containers: `postgres`, `redis`, `api`, and `frontend`.

On first boot the entrypoint automatically:
- Waits for the database to be ready
- Runs all Django migrations
- Creates the admin superuser (from `DJANGO_SUPERUSER_*` env vars)
- Creates the farm service token (printed to the API container logs)
- Collects static files
- Starts the API server (Django dev server in debug mode, Gunicorn otherwise)

### 1.4 Configure Server Hosts and Verify

To view the dashboard on the server itself, the server needs to know how to resolve the local domain names to itself.

1. Navigate to the `scripts/` directory.
2. Right-click `setup_hosts.ps1` and select **Run with PowerShell**.
3. Accept Administrator privileges. When prompted for the IP, simply press **Enter** to use the default (`127.0.0.1`).

Now, open a browser **on the server machine** and check:

| URL | Expected result |
|---|---|
| `http://renderhive.local` | RenderHive dashboard login page |
| `http://server.renderhive.local/api/` | Django REST Framework browsable API |
| `http://server.renderhive.local/admin/` | Django admin panel |

---

## Part 2 — Dashboard Access (Non-Workers)

If a machine (like a supervisor's laptop) only needs to view the web dashboard and won't render jobs, you don't need to install the full worker daemon. Instead, run the included script to configure the domains:

### 2.1 Run the Hosts Setup Script

1. Navigate to the `scripts/` directory.
2. Right-click `setup_hosts.ps1` and select **Run with PowerShell**.
3. The script will request Administrator privileges and ask for the server's LAN IP.

### 2.2 Verify Dashboard Access

Open a browser on any configured machine (worker or dashboard-only) and navigate to:
```
http://renderhive.local
```
You should see the RenderHive login page. Log in with the admin credentials set in `.env`.

---

## Part 3 — Worker Machine Setup

Worker machines are responsible for rendering jobs. You must install the worker daemon, which also automatically configures the network domains required to reach the server.

### 3.1 Obtain the Installer

The pre-built installer is at:
```
worker/Output/RenderHiveWorkerSetup.exe
```

Copy it to a USB drive or shared network folder, then run it on each client machine.

> If `Output/` is empty, build the installer first — see [Appendix A](#appendix-a--building-the-worker-installer).

### 3.2 Run the Installer (on each worker machine)

1. Right-click `RenderHiveWorkerSetup.exe` → **Run as administrator** (admin rights are required to modify the hosts file).
2. Follow the wizard. When prompted for **Server IP Address**, enter the server's LAN IP (e.g. `192.168.100.5`).
3. Complete the installation.

The installer will:
- Install the Worker daemon application to `C:\Program Files\RenderHive\Worker\`
- Add the required domain entries to `C:\Windows\System32\drivers\etc\hosts`.

### 3.3 Get the Farm Token

The worker daemon and Maya plugin both need this token to authenticate against the API. There are two ways to retrieve it:

**Option A — From the container logs** (fastest on first boot):
```bash
docker compose logs api | findstr /i "token"
```

**Option B — From the Django admin panel** (always available):
1. Navigate to `http://renderhive.local/admin/`
2. Log in with your superuser credentials.
3. Go to **Auth Token → Tokens** and look for the token belonging to the `farm_service` user.

Copy this token — you will need it when configuring the worker daemon.

### 3.4 Configure the Worker Daemon

1. Launch **RenderHive Worker** from the desktop or Start menu.
2. Click **Settings** and fill in:
   - **API URL:** `http://server.renderhive.local/api`
   - **API Token:** the farm token from [Step 3.3](#33-get-the-farm-token)
   - **Maya Executable:** path to `Render.exe`, e.g. `C:\Program Files\Autodesk\Maya2025\bin\Render.exe`
3. Click **Save**, then **Start Worker**.

The status indicator will turn green (`ONLINE`) if the connection succeeds.

---

## Part 4 — Maya Plugin Deployment

The Maya plugin lets artists submit render jobs directly from inside Maya. The recommended approach is to serve it from a shared network path so updates roll out automatically.

### 4.1 Set Up a Shared Network Path

Copy the entire `plugins/maya/` folder to a location accessible from all artist machines:
```
\\<server-ip>\Shared\RenderHive\plugins\maya
```
or a mapped drive letter, e.g.:
```
Z:\Pipeline\RenderHive\plugins\maya
```

### 4.2 Configure the Plugin

Open `plugins/maya/config/api_config.template.json` on the shared drive and set:
```json
{
    "base_url": "http://server.renderhive.local",
    "auth": {
        "token": "<paste-farm-token-here>"
    }
}
```
Save the file — all machines reading from the share will pick this up automatically.

### 4.3 Deploy to Artists

Distribute the small `plugins/maya/RenderHive.mod` file to each artist's machine.

1. Open `RenderHive.mod` in a text editor and update the path to match the shared folder:
   ```
   + RenderHive 1.9.7 \\<server-ip>\Shared\RenderHive\plugins\maya
   ```
2. Place the `.mod` file into the artist's Maya modules directory:
   - **Windows:** `C:\Users\<Username>\Documents\maya\modules\`
   *(Create the `modules` folder if it does not exist.)*

3. Restart Maya. The **RenderHive** menu will appear in the Maya menu bar.

> **Alternative:** Artists can also install by dragging `drag_to_maya_install.mel` into the Maya viewport.

---

## Part 5 — First-Login Checklist

After the server is up and at least one client can reach the dashboard:

- [ ] Log in to `http://renderhive.local` with the admin credentials.
- [ ] Go to **Users** → create dashboard accounts for anyone who needs to monitor or manage jobs through the web interface (TDs, supervisors, etc.).
- [ ] Confirm at least one worker shows up in the **Workers** panel after starting the daemon on a client machine.
- [ ] Submit a test render job from the Maya plugin and verify it appears in the **Jobs** queue and gets picked up by the worker.

> **Authentication model:** Dashboard users (humans) log in with a personal username and password. Worker machines and DCC plugins (Maya) are **not** user accounts — they all share the single `farm_service` token. You do not need to create an account per render node.

---

## Ongoing Operations

### Restarting the Stack

```bash
# Stop
docker compose --profile frontend down

# Start (no rebuild needed unless code changed)
docker compose --profile frontend up -d

# Rebuild after code changes
docker compose --profile frontend up --build -d
```

### Viewing Logs

```bash
docker compose logs -f api       # Backend logs
docker compose logs -f frontend  # Next.js logs
docker compose logs -f postgres  # Database logs
```

### Updating to a New Version

```bash
git pull origin develop
docker compose --profile frontend up --build -d
```

Migrations run automatically on startup.

### Resetting the Database

> ⚠️ This deletes all jobs, users, and render history.

```bash
docker compose down -v   # -v removes named volumes (postgres_data)
docker compose --profile frontend up --build -d
```

---

## Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required in prod)* | Django secret key. Must be long and random. |
| `DEBUG` | `False` | Set to `True` for development only. |
| `POSTGRES_DB` | `renderhive` | Database name. |
| `POSTGRES_USER` | `postgres` | Database user. |
| `POSTGRES_PASSWORD` | `postgres` | Database password. **Change this.** |
| `DATABASE_URL` | *(derived)* | Full DSN. Must match `POSTGRES_*` values. |
| `REDIS_URL` | `redis://redis:6379/1` | Redis connection URL. |
| `ALLOWED_HOSTS` | `localhost,...` | Comma-separated list of valid server hostnames/IPs. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Origins allowed to make API requests. |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:3000,...` | Origins trusted for CSRF. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API URL baked into the frontend bundle. Set to `http://server.renderhive.local` for LAN. |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Admin account username (created on first boot). |
| `DJANGO_SUPERUSER_EMAIL` | `admin@renderhive.local` | Admin account email. |
| `DJANGO_SUPERUSER_PASSWORD` | `admin` | Admin account password. **Change this.** |
| `FARM_AGENT_TOKEN` | *(auto-generated)* | Token for worker/plugin auth. Leave blank to auto-generate. |

---

## Appendix A — Building the Worker Installer

If `worker/Output/RenderHiveWorkerSetup.exe` does not exist, build it:

**Prerequisites:** Python 3.11+, [Inno Setup 6](https://jrsoftware.org/isdl.php)

```bash
cd worker
build.bat          # Runs PyInstaller to bundle the worker app
```

Then open `RenderHiveSetup.iss` in the Inno Setup Compiler and click **Build → Compile**. The installer will be written to `worker/Output/`.

---

## Appendix B — Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Browser can't reach `renderhive.local` | Worker installer not run / hosts file not updated | Run `RenderHiveWorkerSetup.exe` as admin on that machine |
| API calls fail in browser (network error) | `NEXT_PUBLIC_API_URL` is `localhost` | Set `NEXT_PUBLIC_API_URL=http://server.renderhive.local` in `.env` and rebuild |
| CORS error mentioning `https://` | Browser's HTTPS-Only Mode is forcing an upgrade | Disable HTTPS-Only Mode / "Always use secure connections" for `.local` domains in your browser settings |
| Worker shows `ERROR` status | Wrong API URL or token | Open Settings in the Worker daemon and verify both values |
| Maya plugin can't connect | `base_url` in `api_config.template.json` not updated | Set `base_url` to `http://server.renderhive.local` and restart Maya |
| `Superuser already exists, skipping` on startup | Expected on second boot onwards | Not an error — safe to ignore |
| Containers won't start | Port 80, 3000, or 8000 already in use | Stop conflicting services or change port mappings in `docker-compose.yml` |
