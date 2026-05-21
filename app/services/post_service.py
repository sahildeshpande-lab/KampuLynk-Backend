"""Compatibility facade for post services.

This module keeps existing imports stable while implementation is split into
focused modules under ``app.services.posts``.
"""

from .posts import *  # noqa: F401,F403

