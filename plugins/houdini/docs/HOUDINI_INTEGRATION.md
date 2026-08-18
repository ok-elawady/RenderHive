# Houdini Integration

## Render sources

RenderHive discovers executable Houdini ROP and Solaris sources. The artist can select multiple sources. The focused source exposes its frame range, renderer/delegate, camera, output, resolution and intermediate USD information; the selection list controls which sources are actually submitted.

## Execution

HIP-driven farm tasks launch Hython with `renderhive_houdini.worker.render_rop`. That script loads the HIP, resolves the selected node, applies only requested job overrides, sets the frame and renders one task frame. USD Render ROP / Karma workflows may launch Husk internally through Houdini, preserving the HIP-driven USD-generation step.

`render_husk.py` remains available for pre-generated USD workflows.

Both runners print `RENDERHIVE_FRAME_START` and `RENDERHIVE_FRAME_DONE` markers so the RenderHive Worker can update frame progress and ETA.

## Multi-source mapping

Two selected sources such as `/stage/characters` and `/stage/environment` become two backend layers under one RenderHive Job. Their node paths, renderers, frame ranges and outputs remain independent.
