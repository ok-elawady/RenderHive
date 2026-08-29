"""RenderHive Django API Standalone Launcher & Management CLI.

Serves the Django API application via Waitress WSGI on Windows,
or handles management commands (--migrate, --createsuperuser, --create-farm-token, --collectstatic).
"""

import os
import sys
from pathlib import Path

# Resolve base paths
if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    BASE_DIR = EXE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent

# Ensure backend modules (apps, config) can be found if not running as frozen single folder
if not getattr(sys, "frozen", False):
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

# Search for environment configuration file
ENV_CANDIDATES = [
    Path.cwd() / "RenderHive.env",
    Path.cwd() / ".env",
    BASE_DIR.parent / "RenderHive.env",
    BASE_DIR.parent / ".env",
    BASE_DIR / "RenderHive.env",
    BASE_DIR / ".env",
]

for env_path in ENV_CANDIDATES:
    if env_path.is_file():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass
        break

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django
django.setup()

from django.core.management import call_command, execute_from_command_line
from config.wsgi import application


def main():
    args = sys.argv[1:]

    if not args:
        # Default: Run WSGI server with waitress
        import waitress

        host = os.environ.get("SERVER_HOST", "127.0.0.1")
        port = int(os.environ.get("SERVER_PORT", 8000))
        threads = int(os.environ.get("WAITRESS_THREADS", 8))

        print(f"Starting RenderHive Django API (Waitress) on http://{host}:{port} ({threads} threads)...")
        waitress.serve(application, host=host, port=port, threads=threads)
        return 0

    cmd = args[0]

    if cmd in ("--migrate", "migrate"):
        print("Running database migrations...")
        call_command("migrate", interactive=False)
        return 0

    elif cmd in ("--createsuperuser", "--create-superuser", "createsuperuser"):
        print("Creating Django superuser...")
        call_command("createsuperuser", interactive=False)
        return 0

    elif cmd in ("--create-farm-token", "--farm-token", "create_farm_token"):
        print("Creating farm service token...")
        call_command("create_farm_token")
        try:
            from rest_framework.authtoken.models import Token
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(username="farm_service")
            token = Token.objects.get(user=user)
            (BASE_DIR / "farm_token.txt").write_text(token.key, encoding="utf-8")
        except Exception as e:
            print(f"Error writing farm_token.txt: {e}")
        return 0

    elif cmd in ("--collectstatic", "--collect-static", "collectstatic"):
        print("Collecting static files...")
        call_command("collectstatic", interactive=False)
        return 0

    elif cmd in ("--celery-worker", "celery-worker", "celery_worker", "worker"):
        import apps.workers.tasks
        import apps.jobs.tasks
        import apps.telemetry.tasks
        from config.celery import app as celery_app

        worker_args = ["worker", "-l", "INFO", "-P", "solo"]
        if len(args) > 1:
            worker_args.extend(args[1:])
        print(f"Starting RenderHive Celery Worker ({' '.join(worker_args)})...")
        celery_app.worker_main(argv=worker_args)
        return 0

    elif cmd in ("--celery-beat", "celery-beat", "celery_beat", "beat"):
        import apps.workers.tasks
        import apps.jobs.tasks
        import apps.telemetry.tasks
        from config.celery import app as celery_app

        beat_args = ["beat", "-l", "INFO", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"]
        if len(args) > 1:
            beat_args.extend(args[1:])
        print(f"Starting RenderHive Celery Beat ({' '.join(beat_args)})...")
        celery_app.start(argv=beat_args)
        return 0

    elif cmd == "--manage":
        # Forward custom management arguments: api_launcher.exe --manage check
        execute_from_command_line([sys.argv[0]] + args[1:])
        return 0

    else:
        # Forward all arguments directly to manage.py CLI
        execute_from_command_line([sys.argv[0]] + args)
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
