"""Shared HTTP router for MARLIN service modules."""

from omni.services.core.routers import ServiceAPIRouter


router = ServiceAPIRouter(tags=["CRIS Render Service"])
