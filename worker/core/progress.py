"""Renderer-aware task progress and ETA estimation.

The worker receives text output from several DCC applications and renderers.
This module turns that output into a stable UI contract without coupling the
main window to Maya, Houdini, Arnold, Karma, or any one log format.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


_EXPLICIT_FRAME_START = re.compile(
    r"RENDERHIVE_FRAME_START\s+frame=(-?\d+)(?:\s+index=(\d+))?(?:\s+total=(\d+))?",
    re.IGNORECASE,
)
_EXPLICIT_FRAME_DONE = re.compile(
    r"RENDERHIVE_FRAME_DONE\s+frame=(-?\d+)(?:\s+index=(\d+))?(?:\s+total=(\d+))?",
    re.IGNORECASE,
)
_FRAME_DONE_PATTERNS = [
    re.compile(r"\bframe\s*[:#=]?\s*(-?\d+)\s+(?:completed|complete|done|finished)\b", re.IGNORECASE),
    re.compile(r"\bfinished\s+(?:rendering\s+)?frame\s*[:#=]?\s*(-?\d+)\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:rendering\s+)?frame\s*[:#=]?\s*(-?\d+)\b", re.IGNORECASE),
]
_FRAME_START_PATTERNS = [
    re.compile(r"\b(?:rendering|render|starting|started)\s+frame\s*[:#=]?\s*(-?\d+)\b", re.IGNORECASE),
    re.compile(r"\bframe\s*[:#=]?\s*(-?\d+)\s+(?:started|starting|rendering)\b", re.IGNORECASE),
    re.compile(r"\b(?:image|sample)\s+at\s+frame\s+(-?\d+)\b", re.IGNORECASE),
]
_RENDER_PERCENT_PATTERNS = [
    re.compile(
        r"\b(?:render(?:ing)?|progress|bucket|sample|pass|done|complete(?:d)?)"
        r"[^%\r\n]{0,45}?\b(\d{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d{1,3}(?:\.\d+)?)\s*%[^\r\n]{0,45}?"
        r"(?:render(?:ing)?|progress|bucket|sample|pass|done|complete(?:d)?)\b",
        re.IGNORECASE,
    ),
]

_PHASE_RULES = [
    (
        "Loading Scene",
        12,
        re.compile(
            r"RENDERHIVE_LOAD|loading\s+(?:scene|file|hip)|opening\s+(?:scene|file)|"
            r"reading\s+(?:scene|file)|file\s+read|scene\s+loaded|hip\s+file",
            re.IGNORECASE,
        ),
    ),
    (
        "Preparing Render",
        18,
        re.compile(
            r"translat(?:e|ing)|export(?:ing)?|generat(?:e|ing)|initiali[sz](?:e|ing)|"
            r"prepar(?:e|ing)|creating\s+(?:scene|universe|render)|RENDERHIVE_OVERRIDES",
            re.IGNORECASE,
        ),
    ),
    (
        "Rendering",
        25,
        re.compile(
            r"RENDERHIVE_RENDER|starting\s+render|rendering\s+(?:frame|image)|"
            r"render\s+started|arnold|karma|husk|mantra|redshift",
            re.IGNORECASE,
        ),
    ),
    (
        "Writing Output",
        92,
        re.compile(
            r"writing\s+(?:image|output|file)|saving\s+(?:image|output|file)|"
            r"image\s+written|output\s+(?:image\s+)?(?:saved|written)|"
            r"RENDERHIVE_WRITE|\.(?:exr|png|jpg|jpeg|tif|tiff|iff)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Finalizing",
        98,
        re.compile(
            r"RENDERHIVE_SUCCESS|finali[sz](?:e|ing)|clean(?:up|ing)|"
            r"render\s+(?:complete|completed|finished)|finished\s+render",
            re.IGNORECASE,
        ),
    ),
]


_PHASE_RANK = {
    "Preparing Task": 0,
    "Resolving Executable": 1,
    "Launching Renderer": 2,
    "Loading Scene": 3,
    "Preparing Render": 4,
    "Rendering": 5,
    "Writing Output": 6,
    "Finalizing": 7,
    "Complete": 8,
    "Stopping": 9,
    "Cancelled": 10,
    "Failed": 10,
}

_PHASE_FLOORS = {
    "Preparing Task": 2,
    "Resolving Executable": 3,
    "Launching Renderer": 6,
    "Loading Scene": 12,
    "Preparing Render": 18,
    "Rendering": 25,
    "Writing Output": 92,
    "Finalizing": 98,
    "Stopping": 0,
    "Failed": 0,
    "Cancelled": 0,
    "Complete": 100,
}


@dataclass
class ProgressSnapshot:
    phase: str
    percent: int
    current_frame: Optional[int]
    total_frames: int
    completed_frames: int
    elapsed_seconds: float
    eta_seconds: Optional[float]
    renderer_percent: Optional[float]
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskProgressTracker:
    """Track one task from process launch through completion.

    Progress is exact when explicit frame-complete markers are available.  For
    a single-frame render, renderer percentages are used when present;
    otherwise the UI uses conservative phase milestones and labels the ETA as
    an estimate rather than inventing a precise renderer percentage.
    """

    def __init__(self, frame_start: int, frame_end: int, frame_step: int = 1, started_at: float | None = None):
        self.frame_start = int(frame_start)
        self.frame_end = int(frame_end)
        self.frame_step = max(1, int(frame_step or 1))
        if self.frame_end >= self.frame_start:
            self.total_frames = max(1, ((self.frame_end - self.frame_start) // self.frame_step) + 1)
        else:
            self.total_frames = 1
        self.started_at = float(started_at if started_at is not None else time.monotonic())
        self.phase = "Preparing Task"
        self.percent = 1
        self.current_frame: Optional[int] = None
        self.completed_frames = 0
        self.renderer_percent: Optional[float] = None
        self.last_line = ""

    def _elapsed(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def _frame_index(self, frame: int) -> Optional[int]:
        value = int(frame)
        if value < self.frame_start or value > self.frame_end:
            return None
        distance = value - self.frame_start
        if distance % self.frame_step != 0:
            return None
        index = distance // self.frame_step
        if index < 0 or index >= self.total_frames:
            return None
        return index

    def _set_phase(self, phase: str, floor: Optional[int] = None) -> None:
        candidate = str(phase or self.phase)
        current_rank = _PHASE_RANK.get(self.phase, 0)
        candidate_rank = _PHASE_RANK.get(candidate, current_rank)
        if candidate in ("Failed", "Cancelled", "Stopping") or candidate_rank >= current_rank:
            self.phase = candidate
        value = _PHASE_FLOORS.get(candidate, 0) if floor is None else int(floor)
        if candidate not in ("Failed", "Cancelled", "Stopping"):
            self.percent = max(self.percent, min(99, value))

    def on_process_event(self, event: str) -> ProgressSnapshot:
        key = str(event or "").strip().lower()
        if key == "resolving_executable":
            self._set_phase("Resolving Executable")
        elif key == "starting_process":
            self._set_phase("Launching Renderer")
        elif key == "process_started":
            self._set_phase("Loading Scene")
        elif key == "stopping_process":
            self._set_phase("Stopping")
        return self.snapshot()

    def _mark_frame_started(self, frame: int) -> None:
        index = self._frame_index(frame)
        if index is None:
            return
        self.current_frame = int(frame)
        self._set_phase("Rendering")
        if self.total_frames > 1:
            # A started frame is not complete.  Keep a small fraction inside
            # the active frame so the bar never jumps ahead of real work.
            base = (index / float(self.total_frames)) * 100.0
            self.percent = max(self.percent, min(97, int(round(base + (20.0 / self.total_frames)))))

    def _mark_frame_done(self, frame: int) -> None:
        index = self._frame_index(frame)
        if index is None:
            return
        self.current_frame = int(frame)
        self.completed_frames = max(self.completed_frames, index + 1)
        self._set_phase("Rendering")
        exact = int(round((self.completed_frames / float(self.total_frames)) * 100.0))
        self.percent = max(self.percent, min(98, exact))
        self.renderer_percent = 100.0

    def _set_renderer_percent(self, value: float) -> None:
        renderer_percent = max(0.0, min(100.0, float(value)))
        self.renderer_percent = renderer_percent
        self._set_phase("Rendering")

        if self.total_frames <= 1:
            # Reserve the first part of the bar for scene setup and the final
            # part for file writing/finalization.
            overall = 20.0 + (renderer_percent * 0.72)
        else:
            index = self._frame_index(self.current_frame) if self.current_frame is not None else None
            active_index = index if index is not None else min(self.completed_frames, self.total_frames - 1)
            overall = ((active_index + renderer_percent / 100.0) / float(self.total_frames)) * 100.0
        self.percent = max(self.percent, min(97, int(round(overall))))

    def on_line(self, line: Any) -> ProgressSnapshot:
        text = str(line or "").strip()
        if not text:
            return self.snapshot()
        self.last_line = text

        explicit_done = _EXPLICIT_FRAME_DONE.search(text)
        if explicit_done:
            self._mark_frame_done(int(explicit_done.group(1)))
        else:
            explicit_start = _EXPLICIT_FRAME_START.search(text)
            if explicit_start:
                self._mark_frame_started(int(explicit_start.group(1)))
            else:
                for pattern in _FRAME_DONE_PATTERNS:
                    match = pattern.search(text)
                    if match:
                        self._mark_frame_done(int(match.group(1)))
                        break
                else:
                    for pattern in _FRAME_START_PATTERNS:
                        match = pattern.search(text)
                        if match:
                            self._mark_frame_started(int(match.group(1)))
                            break

        for pattern in _RENDER_PERCENT_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    self._set_renderer_percent(float(match.group(1)))
                except Exception:
                    pass
                break

        for phase, floor, pattern in _PHASE_RULES:
            if not pattern.search(text):
                continue
            if phase == "Writing Output" and self.total_frames > 1 and self.completed_frames < self.total_frames:
                # Image writes happen once per frame. They must not move the
                # whole chunk to 92% while earlier frames are still rendering.
                self._set_phase("Rendering")
                index = self._frame_index(self.current_frame) if self.current_frame is not None else None
                active_index = index if index is not None else min(self.completed_frames, self.total_frames - 1)
                within_chunk = ((active_index + 0.90) / float(self.total_frames)) * 100.0
                self.percent = max(self.percent, min(97, int(round(within_chunk))))
            elif phase == "Finalizing" and self.total_frames > 1 and self.completed_frames < self.total_frames:
                self._set_phase("Rendering")
            else:
                self._set_phase(phase, floor)

        if "RENDERHIVE_ERROR" in text.upper():
            self.phase = "Failed"
        return self.snapshot()

    def finish(self, success: bool, cancelled: bool = False) -> ProgressSnapshot:
        if cancelled:
            self.phase = "Cancelled"
        elif success:
            self.phase = "Complete"
            self.completed_frames = self.total_frames
            self.current_frame = self.frame_end
            self.renderer_percent = 100.0
            self.percent = 100
        else:
            self.phase = "Failed"
        return self.snapshot()

    def eta_seconds(self) -> Optional[float]:
        elapsed = self._elapsed()
        if elapsed <= 0.0:
            return None

        if self.total_frames > 1 and self.completed_frames > 0:
            remaining_frames = max(0, self.total_frames - self.completed_frames)
            if remaining_frames <= 0:
                return 0.0
            value = (elapsed / float(self.completed_frames)) * remaining_frames
        elif self.percent >= 5 and self.percent < 100:
            value = elapsed * ((100.0 - float(self.percent)) / float(self.percent))
        elif self.percent >= 100:
            return 0.0
        else:
            return None

        # Bad renderer output should never create absurd multi-week ETAs in
        # the UI. Seven days is still intentionally generous for production.
        return max(0.0, min(value, 7.0 * 24.0 * 60.0 * 60.0))

    def _detail(self) -> str:
        if self.phase == "Complete":
            return "Completed {} frame{}".format(self.total_frames, "" if self.total_frames == 1 else "s")
        if self.phase in ("Failed", "Cancelled", "Stopping"):
            return self.phase
        if self.current_frame is not None:
            index = self._frame_index(self.current_frame)
            display_index = (index + 1) if index is not None else max(1, self.completed_frames + 1)
            return "Frame {} of {}  •  Source frame {}".format(display_index, self.total_frames, self.current_frame)
        return self.phase

    def snapshot(self) -> ProgressSnapshot:
        return ProgressSnapshot(
            phase=self.phase,
            percent=max(0, min(100, int(self.percent))),
            current_frame=self.current_frame,
            total_frames=self.total_frames,
            completed_frames=max(0, min(self.total_frames, int(self.completed_frames))),
            elapsed_seconds=self._elapsed(),
            eta_seconds=self.eta_seconds(),
            renderer_percent=self.renderer_percent,
            detail=self._detail(),
        )
