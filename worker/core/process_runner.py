"""Subprocess execution with cancellation, logs, and heartbeat callbacks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .runtime_paths import writable_log_root


_IMAGE_RE = re.compile(
    r"(?:writing|written|saved|saving|output(?:\s+image)?)[^\n]*?"
    r"((?:[A-Za-z]:[\\/]|\\\\|//)[^\r\n\"']+?\.(?:exr|png|iff|jpg|jpeg|tga|tif|tiff|bmp))",
    re.IGNORECASE,
)




def _windows_absolute(path: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", str(path or "")) or str(path or "").startswith(("\\\\", "//")))


def _resolve_executable(command: List[str], env: Dict[str, str]) -> List[str]:
    if not command:
        raise FileNotFoundError("The task command is empty.")

    prepared = [str(item) for item in command]
    executable = prepared[0].strip().strip('"')
    if not executable:
        raise FileNotFoundError("The task executable is empty.")

    if os.path.isabs(executable) or _windows_absolute(executable):
        if not os.path.isfile(executable):
            raise FileNotFoundError("Executable not found: {}".format(executable))
        prepared[0] = executable
        return prepared

    resolved = shutil.which(executable, path=env.get("PATH") or os.environ.get("PATH"))
    if not resolved:
        raise FileNotFoundError(
            "Executable '{}' was not found on PATH. Full task command: {}".format(
                executable, subprocess.list2cmdline(prepared)
            )
        )
    prepared[0] = resolved
    return prepared


@dataclass
class ProcessResult:
    exit_code: int
    log_path: str
    output_image_path: str = ""
    error_tail: str = ""


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def run_process(
    command: List[str],
    task_id: str,
    env: Optional[Dict[str, str]],
    cwd: str,
    is_cancelled: Callable[[], bool],
    heartbeat: Callable[[], None],
    log: Callable[[str], None],
    line_callback: Optional[Callable[[str], None]] = None,
    event_callback: Optional[Callable[[str], None]] = None,
) -> ProcessResult:
    log_root = writable_log_root()
    safe_task_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id or "task"))
    log_path = os.path.join(log_root, "{}.log".format(safe_task_id))

    merged_env = os.environ.copy()
    for key, value in (env or {}).items():
        merged_env[str(key)] = str(value)

    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    output_image_path = ""
    process = None
    try:
        if event_callback is not None:
            try:
                event_callback("resolving_executable")
            except Exception:
                pass
        prepared_command = _resolve_executable(command, merged_env)
        if cwd and not os.path.isdir(cwd):
            raise FileNotFoundError("Working directory does not exist: {}".format(cwd))

        with open(log_path, "w", encoding="utf-8", errors="replace") as handle:
            handle.write("Command: {}\n".format(subprocess.list2cmdline(prepared_command)))
            handle.write("Executable: {}\n".format(prepared_command[0]))
            handle.write("Working Directory: {}\n\n".format(cwd or ""))
            handle.flush()

            if event_callback is not None:
                try:
                    event_callback("starting_process")
                except Exception:
                    pass

            process = subprocess.Popen(
                prepared_command,
                cwd=cwd or None,
                env=merged_env,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                startupinfo=startupinfo,
                bufsize=1,
            )

            if event_callback is not None:
                try:
                    event_callback("process_started")
                except Exception:
                    pass

            last_heartbeat = time.monotonic()
            while True:
                if is_cancelled():
                    log("Cancellation requested. Stopping the DCC process...")
                    if event_callback is not None:
                        try:
                            event_callback("stopping_process")
                        except Exception:
                            pass
                    _terminate_process_tree(process)
                    break

                line = process.stdout.readline() if process.stdout else ""
                if line:
                    handle.write(line)
                    handle.flush()
                    if line_callback is not None:
                        try:
                            line_callback(line.rstrip("\r\n"))
                        except Exception:
                            pass
                    match = _IMAGE_RE.search(line)
                    if match:
                        output_image_path = match.group(1).strip().replace("\\", "/")

                if not line and process.poll() is not None:
                    break

                now = time.monotonic()
                if now - last_heartbeat >= 5.0:
                    heartbeat()
                    last_heartbeat = now
                if not line:
                    time.sleep(0.1)

            exit_code = int(process.wait())
            if process.stdout is not None:
                try:
                    process.stdout.close()
                except Exception:
                    pass
    except Exception as error:
        if process is not None:
            _terminate_process_tree(process)
            if process.stdout is not None:
                try:
                    process.stdout.close()
                except Exception:
                    pass
        with open(log_path, "a", encoding="utf-8", errors="replace") as handle:
            handle.write("\nWorker execution error: {}\n".format(error))
        return ProcessResult(exit_code=-1, log_path=log_path, error_tail=str(error))

    error_tail = ""
    if exit_code != 0:
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
            error_tail = "".join(lines[-8:]).strip()
        except Exception:
            pass

    return ProcessResult(
        exit_code=exit_code,
        log_path=log_path,
        output_image_path=output_image_path,
        error_tail=error_tail,
    )
