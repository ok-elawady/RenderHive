"""Safe entry points called by Houdini menu, shelf and Python Panel files."""


def show():
    """Open or focus the RenderHive bootstrap window."""
    from renderhive_houdini.app import show_window
    return show_window()


def install_runtime_hooks():
    """Register HIP-file callbacks once per Houdini session."""
    from renderhive_houdini.integration.hip_events import install
    install()
