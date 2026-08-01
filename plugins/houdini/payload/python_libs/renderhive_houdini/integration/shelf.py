"""Houdini shelf integration helpers."""


def open_renderhive():
    from renderhive_houdini.bootstrap import show
    return show()
