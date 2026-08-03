from fastapi.testclient import TestClient

from app.main import app


def test_localhost_frontend_cors_preflight_is_allowed() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/chats",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
