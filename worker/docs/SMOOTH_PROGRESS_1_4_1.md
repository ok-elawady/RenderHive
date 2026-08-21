# RenderHive Worker 1.4.1 — Smooth Determinate Progress

The renderer remains the source of truth. The UI now animates from its current
value toward each authoritative renderer update through every whole percentage
instead of jumping from one sparse update to another.

- The label counts 1%, 2%, 3% ... 100% without skipping.
- The progress bar uses a 0..1000 range for sub-percent visual movement.
- A 25 ms visual timer keeps the label and bar synchronized.
- Progress remains monotonic and never moves beyond the latest renderer target.
- A successful task animates through the remaining numbers before settling at
  100%; failed or cancelled tasks preserve their last real target.
