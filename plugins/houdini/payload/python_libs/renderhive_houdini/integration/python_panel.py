"""Houdini Python Panel integration."""


def create_interface():
    """Return an embedded RenderHive widget for a Houdini Python Panel."""
    from renderhive_houdini.bootstrap import install_runtime_hooks
    from renderhive_houdini.ui.main_window import MainWindow

    install_runtime_hooks()
    return MainWindow(parent=None, embedded=True)
