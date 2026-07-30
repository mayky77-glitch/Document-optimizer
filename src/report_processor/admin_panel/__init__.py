"""Local-only Block 18 administrative web panel."""

from .app import create_admin_app, create_app
from .service import AdminPanelService

__all__ = ["AdminPanelService", "create_admin_app", "create_app"]
