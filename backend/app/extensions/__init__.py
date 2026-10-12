"""Enabled feature modules."""

from importlib import import_module

ENABLED_MODULES = (
    "app.extensions.living_stories",
    # New feature modules are added here by scripts/new-extension.py --activate.
)


def load_extensions():
    return [import_module(name) for name in ENABLED_MODULES]


def extension_routers():
    return [
        module.router for module in load_extensions() if getattr(module, "router", None) is not None
    ]
