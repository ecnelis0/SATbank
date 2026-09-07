"""CORS is load-bearing: a rejected preflight renders the whole app as a blank page.

`next dev` picks a different port whenever 3000 is taken, so hardcoding one dev
origin is how the dashboard ends up permanently showing its loading skeleton.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3400",
        "http://localhost:3001",
    ],
)
async def test_a_dev_origin_on_any_port_survives_preflight(client, origin):
    response = await client.request(
        "OPTIONS",
        "/stats",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


async def test_an_unrelated_origin_is_still_refused(client):
    response = await client.request(
        "OPTIONS",
        "/stats",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
