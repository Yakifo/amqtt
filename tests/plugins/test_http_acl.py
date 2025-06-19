from typing import Awaitable

import pytest
from aiohttp import web
from aiohttp.web import Response


class UserAuthView(web.View):
    async def get(self) -> Response:
        return web.Response(status=400)

    async def post(self):
        return web.json_response({"hello": "world"})



@pytest.fixture
def http_acl_server():
    app = web.Application()
    app.add_routes([
        web.view('/', UserAuthView),
    ])