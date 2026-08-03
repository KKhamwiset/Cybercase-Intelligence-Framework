import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main as main_module


def _fastapi_app() -> FastAPI:
    application = main_module.app
    while not isinstance(application, FastAPI):
        application = application.app
    return application


def test_only_health_and_chat_api_routes_are_registered() -> None:
    api_routes = {
        (method, route.path)
        for route in _fastapi_app().routes
        if route.path.startswith("/api/")
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    assert api_routes == {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/chats"),
        ("POST", "/api/v1/chats"),
        ("GET", "/api/v1/chats/{thread_id}"),
        ("PATCH", "/api/v1/chats/{thread_id}"),
        ("DELETE", "/api/v1/chats/{thread_id}"),
        ("POST", "/api/v1/chats/{thread_id}/messages"),
        ("GET", "/api/v1/chats/{thread_id}/runs/{run_id}"),
    }


def test_legacy_route_prefixes_return_not_found_without_startup() -> None:
    client = TestClient(main_module.app)

    for path in (
        "/api/v1/users",
        "/api/v1/rag",
        "/api/v1/cases",
        "/api/v1/reports",
    ):
        assert client.get(path).status_code == 404


def test_startup_tolerates_database_unavailability_without_live_database(
    monkeypatch,
) -> None:
    class _FailingConnection:
        async def __aenter__(self):
            raise OSError("database intentionally unavailable")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class _FakeEngine:
        def __init__(self) -> None:
            self.disposed = False

        def connect(self) -> _FailingConnection:
            return _FailingConnection()

        async def dispose(self) -> None:
            self.disposed = True

    fake_engine = _FakeEngine()
    monkeypatch.setattr(main_module, "engine", fake_engine)

    async def exercise_lifespan() -> None:
        async with main_module.lifespan(_fastapi_app()):
            pass

    asyncio.run(exercise_lifespan())

    assert fake_engine.disposed is True
