# RenderHive 🐝

Distributed rendering management platform designed for modern 3D pipeline workflows. RenderHive coordinates render jobs, schedules tasks across workers, and integrates seamlessly with digital content creation (DCC) tools.

---

## 🏗️ Project Structure

This repository is organized as a monorepo containing the following main components:

| Component    | Path                      | Description                                                    | Tech Stack / Technologies                                     |
| :----------- | :------------------------ | :------------------------------------------------------------- | :------------------------------------------------------------ |
| **Frontend** | [`frontend/`](./frontend) | Web dashboard for monitoring jobs, workers, and user settings. | Next.js 16 (App Router), React 19, Tailwind CSS v4, Shadcn UI |
| **Backend**  | [`backend/`](./backend)   | Central orchestration API server and scheduler.                | Django REST Framework, Celery, Redis / RabbitMQ               |
| **Plugins**  | [`plugins/`](./plugins)   | DCC Integrations. Currently hosts Autodesk Maya integration.   | Python, PySide, MEL, Maya Commands                            |

---

## 🎨 Key Features

- **Distributed Orchestration**: Manage render workers, assign priorities, and balance render loads dynamically.
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
- Node.js (v20+ recommended)
- `pnpm` (package manager for the frontend)
- Autodesk Maya (for using the Maya submitter/worker plugins)

### 🐳 Running the Backend Services (API, Postgres, Redis)

To launch the orchestration backend:

1. Copy `.env.example` to `.env` in the root directory:
   ```bash
   cp .env.example .env
   ```
2. Run the Docker Compose stack:
   ```bash
   docker compose up --build
   ```
3. The backend API will be available at [http://localhost:8000](http://localhost:8000).

### 💻 Running the Frontend

To launch the web dashboard:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   pnpm install
   ```
3. Start the local development server:
   ```bash
   pnpm dev
   ```
4. Open your browser and navigate to [http://localhost:3000](http://localhost:3000).

---

## 🔌 DCC Integrations

### Autodesk Maya

The Maya plugin allows artists to submit jobs directly from inside Maya.

- **Installer**: Drag and drop [`drag_to_maya_install.mel`](./plugins/maya/drag_to_maya_install.mel) into the Maya viewport, or run [`renderhive_installer.py`](./plugins/maya/renderhive_installer.py).
- **Submitter**: Run the submitter tool to configure frames, cameras, render layers, and export job packages to the hive.
