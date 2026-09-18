"""Optional NVIDIA Kit Services exchange and isolated actor control."""
import omni.ext
from omni.services.core import main
from omni.services.core.routers import ServiceAPIRouter
from .exchange import StepBuffer, validate_step


class GamaBridgeExtension(omni.ext.IExt):
    def on_startup(self, _ext_id):
        self._buffer = StepBuffer()
        self._actor = None
        self._router = ServiceAPIRouter(tags=["MARLIN GAMA preview exchange"])

        @self._router.post("/integration/gama/validate")
        async def validate(payload: dict):
            try:
                return {"ok": True, "snapshot": validate_step(payload), "rendered": False}
            except ValueError as error:
                return {"ok": False, "error": str(error), "rendered": False}

        @self._router.post("/integration/gama/steps")
        async def accept(payload: dict):
            try:
                return {"ok": True, **self._buffer.accept(payload)}
            except ValueError as error:
                return {"ok": False, "error": str(error), "rendered": False}

        @self._router.get("/integration/gama/status")
        async def status():
            return {"ok": True, "mode": "validation_only", "rendered": False,
                    "accepted_steps": self._buffer.accepted_steps,
                    "latest": self._buffer.latest}

        @self._router.post("/integration/gama/reset")
        async def reset():
            self._buffer.reset()
            return {"ok": True, "mode": "validation_only", "rendered": False}

        def actor():
            if self._actor is None:
                from .actor import IsolatedActor
                self._actor = IsolatedActor()
            return self._actor

        def context():
            import omni.usd
            from cris.madil.render_service import capture_state
            return omni.usd.get_context().get_stage(), capture_state.paused

        @self._router.post("/integration/gama/actor/acquire")
        async def acquire():
            try:
                stage, paused = context()
                return {"ok": True, **actor().acquire(stage, paused)}
            except ValueError as error:
                return {"ok": False, "error": str(error)}

        @self._router.post("/integration/gama/actor/step")
        async def apply(payload: dict):
            try:
                if set(payload) != {"ownership_token", "step"}:
                    raise ValueError("Expected ownership_token and step only")
                stage, paused = context()
                return {"ok": True, **actor().apply(stage, payload["ownership_token"], payload["step"], paused)}
            except ValueError as error:
                return {"ok": False, "error": str(error)}

        @self._router.post("/integration/gama/actor/release")
        async def release(payload: dict):
            try:
                if set(payload) != {"ownership_token"}:
                    raise ValueError("Expected ownership_token only")
                _, paused = context()
                actor().release(payload["ownership_token"], paused)
                return {"ok": True, "released": True}
            except ValueError as error:
                return {"ok": False, "error": str(error)}

        @self._router.get("/integration/gama/actor/status")
        async def actor_status():
            return {"ok": True, **actor().status()}

        @self._router.get("/integration/gama/marine/audit")
        async def marine_audit():
            from .marine_check import audit
            return await audit()

        @self._router.post("/integration/gama/actor/capture")
        async def actor_capture(payload: dict):
            try:
                if set(payload) != {"ownership_token"}:
                    raise ValueError("Expected ownership_token only")
                from .marine_check import capture
                return await capture(actor(), payload["ownership_token"])
            except (ValueError, RuntimeError) as error:
                return {"ok": False, "error": str(error)}

        main.register_router(self._router)

    def on_shutdown(self):
        main.deregister_router(self._router)
        if self._actor is not None:
            self._actor.close()
        self._buffer.reset()
