# RenderHive 🐝

Distributed rendering management platform designed for modern 3D pipeline workflows. RenderHive coordinates render jobs, schedules tasks across workers, and integrates seamlessly with digital content creation (DCC) tools.

---

## 🏗️ Project Structure

This repository is organized as a monorepo containing the following main components:

| Component         | Path                                          | Description                                                              | Tech Stack / Technologies                                     |
| :---------------- | :-------------------------------------------- | :----------------------------------------------------------------------- | :------------------------------------------------------------ |
| **Frontend**      | [`frontend/`](./frontend)                     | Web dashboard for monitoring jobs, workers, and user settings.           | Next.js 16 (App Router), React 19, Tailwind CSS v4, Shadcn UI |
| **Backend**       | [`backend/`](./backend)                       | Central orchestration API server and task scheduler.                     | Django REST Framework, Celery, Redis                          |
| **Worker**        | [`worker/`](./worker)                         | Desktop application that runs on each render node.                       | Python, PySide6 (Qt), psutil                                  |
| **AI Service**  | [`services/ai_service/`](./services/ai_service) | LLM-powered service for intelligent task dispatch and log explanation.     | FastAPI, llama-cpp-python                                     |
| **Plugins**       | [`plugins/`](./plugins)                       | DCC Integrations. Currently hosts Autodesk Maya integration.             | Python, PySide, MEL, Maya Commands                            |
| **Server Installer** | [`server/`](./server)                         | Fully automated Windows installer for local/on-premise deployment.       | Inno Setup, PowerShell, Batch, PyInstaller                    |

---

## 🎨 Key Features

- **Distributed Orchestration**: Manage render workers, assign priorities, and balance render loads dynamically.
- **AI-Augmented Scheduling**: An optional local LLM service ([`services/ai_service/`](./services/ai_service)) acts as a tie-breaker when multiple tasks are equally viable, using live worker capabilities (CPU load, GPU VRAM, memory) to make the best dispatch decision. Falls back to deterministic scoring when the AI service is unavailable.
- **Next-Gen Web Dashboard**: Clean, modern interface designed with Tailwind CSS v4 and Shadcn UI.
- **Autodesk Maya Plugin Integration**:
  - Drag-and-drop installation (`drag_to_maya_install.mel`).
  - PySide-based Job Submitter UI for Maya artists.
  - Validation engine to check scenes before submitting.
  - Dedicated worker scripts to execute command-line renders.

---

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js (v20+ recommended) — only needed for frontend development outside Docker
- `pnpm` — only needed for frontend development outside Docker
- Autodesk Maya (for using the Maya submitter/worker plugins)

### 🐳 Running with Docker Compose (Recommended)

RenderHive uses Docker Compose **profiles** to let you start only the components you need.

**1. Set up your environment:**
```bash
cp .env.example .env
# Edit .env as needed for your environment
```

**2. Choose a profile combination:**

| Command | What starts |
|---|---|
| `docker compose up --build` | API + Postgres + Redis (minimum) |
| `docker compose --profile frontend up --build` | + Frontend (Next.js) + Nginx |
| `docker compose --profile ai up --build` | + AI Scheduler (LLM tie-breaker) |
| `docker compose --profile frontend --profile ai up --build` | Everything |

```bash
# Example — full stack with frontend and AI:
docker compose --profile frontend --profile ai up --build
```

**Services and ports:**

| Service | Port | Profile |
|---|---|---|
| Backend API | [http://localhost:8000](http://localhost:8000) | *(always)* |
| Frontend | [http://localhost:3000](http://localhost:3000) | `frontend` |
| Nginx (reverse proxy) | [http://localhost:80](http://localhost:80) | `frontend` |
| AI Scheduler | [http://localhost:8001](http://localhost:8001) | `ai` |

> **AI Service note:** Requires a GGUF model file. Without one it runs in mock mode (useful for dev). See [`services/ai_service/README.md`](./services/ai_service/README.md) for model setup.

---

### 💿 Running with Windows Installer (Easy Mode / Local Deployments)

RenderHive provides a fully standalone Windows installer that automatically configures all required services (PostgreSQL, Redis, Nginx, Django API, Next.js Frontend, and the AI Service) as Windows Background Services.

**Installation Steps:**
1. Run the `RenderHive Server Setup.exe` installer (located in `server/Output/`).
2. Follow the prompts to specify the installation directory, data directory, and Server IP.
3. The installer automatically extracts and configures PostgreSQL 16, Redis, Nginx, Django API, Next.js frontend, and the AI Service, registering them all as Windows services using NSSM.
4. Once installed, open your browser to `http://renderhive.local` (if on the host machine) or via your server's IP.

**Building the Installer from Source:**
If you are developing or need to compile the installer yourself:
1. Open a terminal in the `server/` directory.
2. Run `.\build.bat` (requires Python and `pnpm`). This builds the PyInstaller executables for the API, AI Service, Manager GUI, and exports the Next.js frontend.
3. Open `RenderHiveServerSetup.iss` in **Inno Setup 6 or 7** and click **Compile**.
4. The final `.exe` will be generated in `server/Output/`.

### 💻 Running the Frontend Locally (without Docker)

If you prefer hot-reload outside of Docker:

1. Install dependencies:
   ```bash
   cd frontend
   pnpm install
   ```
2. Start the dev server:
   ```bash
   pnpm dev
   ```
3. Open [http://localhost:3000](http://localhost:3000).

---

## 🔌 DCC Integrations

### Autodesk Maya

The Maya plugin allows artists to submit jobs directly from inside Maya.

- **Installer**: Drag and drop [`drag_to_maya_install.mel`](./plugins/maya/drag_to_maya_install.mel) into the Maya viewport, or run [`renderhive_installer.py`](./plugins/maya/renderhive_installer.py).
- **Submitter**: Run the submitter tool to configure frames, cameras, render layers, and export job packages to the hive.
