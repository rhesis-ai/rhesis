# ruff: noqa: E501
# This file contains embedded HTML/SVG templates that cannot be reformatted
import asyncio
import functools
import json
import logging
import os
import pathlib

import nest_asyncio

nest_asyncio.apply()

import aiohttp  # noqa: E402
import aiohttp_security  # noqa: E402
import aiohttp_session  # noqa: E402
import aiohttp_session.cookie_storage  # noqa: E402
import cryptography.fernet  # noqa: E402
from aiohttp import web  # noqa: E402

# from aiohttp_session import SimpleCookieStorage, session_middleware
from aiohttp_security import (  # noqa: E402
    SessionIdentityPolicy,
    remember,
)
from aiohttp_security import (  # noqa: E402
    setup as setup_security,
)
from aiohttp_security.abc import AbstractAuthorizationPolicy  # noqa: E402

from ._test_tree import TestTree  # noqa: E402

log = logging.getLogger(__name__)


def serve(
    test_tree_browsers,
    host="localhost",
    port=8080,
    static_dir=None,
    authenticate=lambda user, password: True,
    authorize=lambda user, location: True,
    auth_duration=60 * 60 * 8,
    ssl_crt=None,
    ssl_key=None,
):
    """Serves the interface at the given host and port."""
    log.debug(f"serve(test_tree_browsers={test_tree_browsers})")

    if isinstance(test_tree_browsers, TestTree):
        raise Exception(
            "You cannot serve a TestTree directly! "
            "You need to call it with a scorer like test_tree(scorer)."
        )

    if isinstance(authenticate, dict):
        auth_dict = authenticate

        def check_pass(user, password):
            return auth_dict.get(user, object()) == password

        authenticate = check_pass

    loop = asyncio.get_event_loop()

    if not hasattr(test_tree_browsers, "interface_event") and callable(test_tree_browsers):
        test_tree_browsers = functools.lru_cache(maxsize=None)(test_tree_browsers)

    async def send_ws_data(ws, str_data):
        await ws.send_str(str_data)

    async def topic_handler(request):
        log.debug(f"topic_handler({request})")
        logged_in = not await aiohttp_security.is_anonymous(request)

        if not logged_in:
            user = request.rel_url.query.get("user", "anonymous")
            if authenticate(user, None):
                redirect_response = web.HTTPFound(str(request.rel_url))
                await remember(request, redirect_response, user)
                return redirect_response
            else:
                raise web.HTTPFound(f"/_login?user={user}&sendback={str(request.rel_url)}")
        else:
            user = await aiohttp_security.authorized_userid(request)
            if hasattr(test_tree_browsers, "interface_event"):
                prefix = ""
                test_tree_browser = test_tree_browsers
                test_tree_name = "fake"
            else:
                test_tree_name = request.match_info["test_tree"]
                prefix = "/" + test_tree_name
                if callable(test_tree_browsers):
                    test_tree_browser = test_tree_browsers(test_tree_name)
                else:
                    test_tree_browser = test_tree_browsers.get(test_tree_name, None)

                # make sure we found the given test
                if not hasattr(test_tree_browser, "interface_event"):
                    log.debug(f"The test tree we found was not valid: {test_tree_browsers}")
                    raise web.HTTPNotFound()
            test_tree_browser.user = user
            test_tree_browser.name = test_tree_name

            interface_html = f"""
<html>
  <head>
    <title>Adaptive Testing</title>
  </head>
  <body style="font-family: Helvetica Neue, Helvetica, Arial, sans-serif; margin-right: 20px; font-size: 14px;">
    {test_tree_browser._repr_html_(prefix=prefix, environment="web", websocket_server=prefix + "/_ws")}
  </body>
</html>
"""

            return web.Response(text=interface_html, content_type="text/html")

    async def static_handler(request):
        logged_in = not await aiohttp_security.is_anonymous(request)
        log.debug(f"static_handler({request})")
        if not logged_in:
            user = request.rel_url.query.get("user", "anonymous")
            if authenticate(user, None):
                redirect_response = web.HTTPFound(str(request.rel_url))
                await remember(request, redirect_response, user)
                return redirect_response
            else:
                raise web.HTTPFound(f"/_login?user={user}&sendback={str(request.rel_url)}")
        else:
            if request.raw_path == "/favicon.ico":
                file_path = pathlib.Path(__file__).parent.absolute()
                return web.FileResponse(file_path / "resources" / "favicon.png")
            elif "file_path" in request.match_info:
                file_path = os.path.join(
                    static_dir, *request.match_info["file_path"].replace("..", "").split("/")
                )
                return web.FileResponse(file_path)
            else:
                raise web.HTTPNotFound()
            # with open(file_path) as f:
            #     file_data = f.read()
            # if file_path.endswith(".png"):
            #     content_type = "image/png"
            # elif file_path.endswith(".gif"):
            #     content_type = "image/gif"
            # elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            #     content_type = "image/jpeg"
            # elif file_path.endswith(".js"):
            #     content_type = "application/javascript"
            # else:
            #     content_type = "text/html"
            # return web.Response(text=file_data, content_type=content_type)

    async def login_handler(request):
        sendback = request.rel_url.query.get("sendback", "/")
        user = request.rel_url.query.get("user", "")
        return web.Response(
            text=f"""
<html>
  <head>
    <title>Adaptive Testing Login</title>
  </head>
  <body style="font-family: arial">
    <form method="post" action="/_auth" style="margin-top: 80px">
      <table style="margin-left: auto; margin-right: auto;">
        <tr>
          <td colspan="2" style="text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 15px;">
            <svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px"
  viewBox="0 0 96.431 28.308" style="enable-background:new 0 0 96.431 28.308; width: 250px; margin-bottom: 20px;" xml:space="preserve">
<g>
 <path style="fill:#231F20;" d="M8.16,21.516c-1.28,0-2.428-0.291-3.444-0.876C3.7,20.057,2.9,19.256,2.316,18.24
  S1.44,16.084,1.44,14.82c0-1.28,0.292-2.428,0.876-3.444c0.584-1.016,1.384-1.815,2.4-2.4C5.732,8.393,6.88,8.1,8.16,8.1
  c1.28,0,2.424,0.293,3.432,0.876c1.008,0.585,1.804,1.385,2.388,2.4c0.584,1.017,0.876,2.164,0.876,3.444l-0.6,0.96
  c0,1.088-0.268,2.063-0.804,2.928c-0.537,0.864-1.26,1.548-2.172,2.052C10.368,21.264,9.328,21.516,8.16,21.516z M8.16,20.172
  c1.008,0,1.908-0.235,2.7-0.708c0.792-0.472,1.416-1.111,1.872-1.92c0.456-0.808,0.684-1.716,0.684-2.724
  c0-1.024-0.228-1.94-0.684-2.748s-1.08-1.448-1.872-1.92s-1.692-0.708-2.7-0.708c-0.992,0-1.888,0.236-2.688,0.708
  c-0.8,0.472-1.432,1.112-1.896,1.92C3.112,12.88,2.88,13.796,2.88,14.82c0,1.008,0.232,1.916,0.696,2.724
  c0.464,0.809,1.096,1.448,1.896,1.92C6.272,19.937,7.168,20.172,8.16,20.172z M14.136,21.372c-0.208,0-0.38-0.068-0.516-0.204
  c-0.136-0.136-0.204-0.308-0.204-0.516V16.26l0.456-1.439h0.984v5.832c0,0.208-0.064,0.38-0.192,0.516
  C14.536,21.304,14.36,21.372,14.136,21.372z"/>
 <path style="fill:none;" d="M24.456,21.516c-1.28,0-2.428-0.291-3.444-0.876c-1.016-0.583-1.816-1.384-2.4-2.399
  s-0.876-2.164-0.876-3.444c0-1.279,0.292-2.424,0.876-3.432s1.384-1.804,2.4-2.389C22.028,8.393,23.176,8.1,24.456,8.1
  c1.152,0,2.188,0.249,3.108,0.744c0.92,0.496,1.636,1.16,2.148,1.992V3.348c0-0.224,0.068-0.399,0.204-0.527
  c0.136-0.128,0.308-0.192,0.516-0.192c0.224,0,0.399,0.064,0.528,0.192c0.128,0.128,0.192,0.304,0.192,0.527V14.94
  c-0.016,1.248-0.32,2.368-0.912,3.359c-0.592,0.992-1.388,1.776-2.388,2.353C26.852,21.229,25.72,21.516,24.456,21.516z
   M24.456,20.172c1.008,0,1.908-0.235,2.7-0.708c0.792-0.472,1.416-1.111,1.872-1.92c0.456-0.808,0.684-1.724,0.684-2.748
  c0-1.023-0.228-1.936-0.684-2.735c-0.456-0.801-1.08-1.437-1.872-1.908s-1.692-0.708-2.7-0.708c-0.992,0-1.888,0.236-2.688,0.708
  c-0.8,0.472-1.432,1.107-1.896,1.908c-0.464,0.8-0.696,1.712-0.696,2.735c0,1.024,0.232,1.94,0.696,2.748
  c0.464,0.809,1.096,1.448,1.896,1.92C22.568,19.937,23.464,20.172,24.456,20.172z"/>
 <path style="fill:#231F20;" d="M41.472,21.516c-1.28,0-2.428-0.291-3.444-0.876c-1.016-0.583-1.816-1.384-2.4-2.399
  s-0.876-2.156-0.876-3.42c0-1.28,0.292-2.428,0.876-3.444c0.584-1.016,1.384-1.815,2.4-2.4C39.043,8.393,40.191,8.1,41.472,8.1
  c1.28,0,2.424,0.293,3.432,0.876c1.008,0.585,1.804,1.385,2.388,2.4c0.584,1.017,0.876,2.164,0.876,3.444l-0.6,0.96
  c0,1.088-0.268,2.063-0.804,2.928c-0.537,0.864-1.26,1.548-2.172,2.052C43.68,21.264,42.639,21.516,41.472,21.516z M41.472,20.172
  c1.008,0,1.908-0.235,2.7-0.708c0.792-0.472,1.416-1.111,1.872-1.92c0.456-0.808,0.684-1.716,0.684-2.724
  c0-1.024-0.228-1.94-0.684-2.748s-1.08-1.448-1.872-1.92s-1.692-0.708-2.7-0.708c-0.992,0-1.888,0.236-2.688,0.708
  c-0.8,0.472-1.432,1.112-1.896,1.92c-0.464,0.808-0.696,1.724-0.696,2.748c0,1.008,0.232,1.916,0.696,2.724
  c0.464,0.809,1.096,1.448,1.896,1.92C39.583,19.937,40.479,20.172,41.472,20.172z M47.448,21.372c-0.208,0-0.38-0.068-0.516-0.204
  c-0.136-0.136-0.204-0.308-0.204-0.516V16.26l0.456-1.439h0.984v5.832c0,0.208-0.064,0.38-0.192,0.516
  C47.847,21.304,47.671,21.372,47.448,21.372z"/>
 <path style="fill:#58595B;" d="M50.735,10.021c-0.192,0-0.348-0.061-0.468-0.181c-0.12-0.12-0.18-0.275-0.18-0.468
  s0.06-0.348,0.18-0.468c0.12-0.12,0.276-0.181,0.468-0.181h6.504c0.192,0,0.348,0.061,0.468,0.181s0.18,0.275,0.18,0.468
  s-0.06,0.348-0.18,0.468s-0.275,0.181-0.468,0.181H50.735z M57.144,21.372c-0.881-0.016-1.665-0.22-2.353-0.612
  c-0.688-0.392-1.224-0.936-1.607-1.632c-0.384-0.696-0.576-1.483-0.576-2.364V4.812c0-0.225,0.068-0.404,0.204-0.54
  c0.136-0.136,0.308-0.204,0.516-0.204c0.224,0,0.404,0.068,0.54,0.204s0.204,0.315,0.204,0.54v11.951
  c0,0.929,0.288,1.685,0.864,2.269c0.575,0.584,1.319,0.876,2.231,0.876h0.528c0.224,0,0.403,0.068,0.54,0.204
  c0.136,0.136,0.204,0.315,0.204,0.54c0,0.208-0.068,0.38-0.204,0.516c-0.137,0.136-0.316,0.204-0.54,0.204H57.144z"/>
 <path style="fill:#58595B;" d="M67.247,21.492c-1.264,0-2.388-0.284-3.372-0.853c-0.984-0.567-1.756-1.355-2.316-2.363
  c-0.56-1.008-0.84-2.16-0.84-3.456c0-1.312,0.265-2.468,0.792-3.468c0.528-1,1.256-1.788,2.185-2.364
  c0.928-0.576,1.992-0.864,3.191-0.864c1.185,0,2.232,0.276,3.145,0.828s1.624,1.312,2.136,2.28s0.768,2.084,0.768,3.348
  c0,0.208-0.063,0.372-0.191,0.492s-0.296,0.18-0.504,0.18H61.679v-1.248h10.944l-1.056,0.792c0.031-1.04-0.145-1.96-0.528-2.76
  s-0.933-1.428-1.644-1.884c-0.713-0.456-1.549-0.685-2.509-0.685c-0.912,0-1.724,0.229-2.436,0.685s-1.272,1.084-1.68,1.884
  c-0.408,0.8-0.612,1.728-0.612,2.784c0,1.04,0.216,1.96,0.647,2.76c0.433,0.8,1.032,1.428,1.801,1.884
  c0.768,0.456,1.647,0.685,2.64,0.685c0.624,0,1.252-0.108,1.884-0.324s1.132-0.5,1.5-0.853c0.128-0.128,0.284-0.195,0.468-0.203
  c0.185-0.009,0.34,0.044,0.469,0.155c0.176,0.145,0.268,0.305,0.275,0.48s-0.068,0.336-0.228,0.479
  c-0.513,0.465-1.181,0.849-2.004,1.152C68.787,21.34,67.999,21.492,67.247,21.492z"/>
 <path style="fill:#58595B;" d="M80.519,21.516c-0.832,0-1.704-0.151-2.616-0.455c-0.911-0.305-1.672-0.816-2.279-1.536
  c-0.129-0.16-0.181-0.332-0.156-0.517c0.024-0.184,0.124-0.34,0.3-0.468c0.16-0.111,0.332-0.151,0.517-0.12
  c0.184,0.032,0.331,0.12,0.443,0.264c0.464,0.545,1.028,0.925,1.692,1.141s1.388,0.324,2.172,0.324c1.344,0,2.296-0.24,2.855-0.721
  c0.561-0.479,0.841-1.039,0.841-1.68c0-0.624-0.301-1.14-0.9-1.548s-1.524-0.7-2.771-0.876c-1.601-0.224-2.784-0.656-3.553-1.296
  c-0.768-0.64-1.151-1.384-1.151-2.232c0-0.8,0.199-1.476,0.6-2.027c0.399-0.553,0.948-0.969,1.644-1.248
  C78.851,8.24,79.646,8.1,80.543,8.1c1.088,0,2.008,0.196,2.76,0.589c0.752,0.392,1.359,0.916,1.824,1.571
  c0.128,0.16,0.172,0.333,0.132,0.517s-0.164,0.332-0.372,0.443c-0.16,0.081-0.328,0.104-0.504,0.072
  c-0.177-0.032-0.328-0.128-0.456-0.288c-0.4-0.512-0.884-0.899-1.452-1.164c-0.568-0.264-1.228-0.396-1.979-0.396
  c-1.009,0-1.792,0.216-2.353,0.647c-0.56,0.433-0.84,0.952-0.84,1.561c0,0.416,0.116,0.779,0.348,1.092
  c0.232,0.312,0.612,0.576,1.141,0.792c0.527,0.216,1.231,0.388,2.111,0.516c1.2,0.16,2.148,0.433,2.845,0.816
  c0.695,0.384,1.191,0.828,1.487,1.332s0.444,1.044,0.444,1.62c0,0.752-0.24,1.408-0.72,1.968c-0.48,0.561-1.112,0.988-1.896,1.284
  S81.431,21.516,80.519,21.516z"/>
 <path style="fill:#58595B;" d="M87.887,10.021c-0.192,0-0.349-0.061-0.468-0.181c-0.12-0.12-0.181-0.275-0.181-0.468
  s0.061-0.348,0.181-0.468c0.119-0.12,0.275-0.181,0.468-0.181h6.504c0.192,0,0.348,0.061,0.468,0.181s0.18,0.275,0.18,0.468
  s-0.06,0.348-0.18,0.468s-0.275,0.181-0.468,0.181H87.887z M94.295,21.372c-0.881-0.016-1.665-0.22-2.353-0.612
  c-0.688-0.392-1.224-0.936-1.607-1.632c-0.385-0.696-0.576-1.483-0.576-2.364V4.812c0-0.225,0.067-0.404,0.204-0.54
  c0.136-0.136,0.308-0.204,0.516-0.204c0.224,0,0.404,0.068,0.54,0.204s0.204,0.315,0.204,0.54v11.951
  c0,0.929,0.288,1.685,0.864,2.269c0.575,0.584,1.319,0.876,2.231,0.876h0.528c0.224,0,0.403,0.068,0.54,0.204
  c0.136,0.136,0.204,0.315,0.204,0.54c0,0.208-0.068,0.38-0.204,0.516c-0.137,0.136-0.316,0.204-0.54,0.204H94.295z"/>
</g>
<g>
 <path style="fill:none;stroke:#000000;stroke-width:1.3;stroke-linecap:round;stroke-miterlimit:10;" d="M29.944,17.481
  c-0.992,1.998-3.053,3.371-5.434,3.371c-3.349,0-6.063-2.715-6.063-6.063"/>

  <polyline style="fill:none;stroke:#000000;stroke-width:1.3;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:10;" points="
  16.884,14.93 18.475,13.34 20.065,14.93  "/>
 <path style="fill:none;stroke:#000000;stroke-width:1.3;stroke-linecap:round;stroke-miterlimit:10;" d="M19.025,11.617
  c0.992-1.998,3.053-3.371,5.434-3.371c3.349,0,6.063,2.715,6.063,6.063"/>

  <polyline style="fill:none;stroke:#000000;stroke-width:1.3;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:10;" points="
  32.085,14.168 30.494,15.759 28.904,14.168  "/>

  <line style="fill:none;stroke:#000000;stroke-width:1.3;stroke-linecap:round;stroke-miterlimit:10;" x1="30.525" y1="14.924" x2="30.525" y2="3.205"/>
</g>
</svg>
          </td>
        </tr>
        <tr>
          <td style="width: 100px; text-align: right">Username:</td><td style="width: 250px"><input type="text" name="user" style="width: 100%" value="{user}"></td>
        </tr>
        <tr>
          <td style="text-align: right">Password:</td><td><input type="password" name="password" style="width: 100%"></td>
        </tr>
        <tr>
          <td colspan="2" style="text-align: right"><input type="submit" value="Login"></td>
        </tr>
      </table>
      <input type="hidden" name="sendback" value="{sendback}">
    </form>
    </div>
  </body>
</html>
""",
            content_type="text/html",
        )

    async def auth_handler(request):
        post_params = await request.post()
        sendback = post_params.get("sendback", "/")
        user = post_params.get("user", None)
        password = post_params.get("password", None)

        if authenticate(user if user is not None else "anonymous", password):
            redirect_response = web.HTTPFound(sendback)
            await remember(request, redirect_response, user if user is not None else "anonymous")
            return redirect_response
        else:
            raise web.HTTPFound(
                f"/_login?{'user=' + user + '&' if user is not None else ''}sendback={sendback}"
            )

    async def websocket_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # build a WebSocket comm object
        class WebSocketComm:
            pass

        def ws_send(data):
            loop.run_until_complete(send_ws_data(ws, json.dumps(data)))

        comm = WebSocketComm()
        comm.send = ws_send

        if hasattr(test_tree_browsers, "_repr_html_"):
            test_tree_browser = test_tree_browsers
        else:
            test_tree_name = request.match_info["test_tree"]
            if callable(test_tree_browsers):
                test_tree_browser = test_tree_browsers(test_tree_name)
            else:
                test_tree_browser = test_tree_browsers[test_tree_name]
        test_tree_browser.comm = comm

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == "close":
                    user = getattr(test_tree_browser, "user", None)
                    name = getattr(test_tree_browser, "name", None)
                    log.debug(f"Closing WebSocket for user '{user}' for test tree '{name}'!")
                    await ws.close()
                else:
                    data = json.loads(msg.data)
                    user = getattr(test_tree_browser, "user", None)
                    name = getattr(test_tree_browser, "name", None)
                    log.info(f"WebSocket message from user '{user}' for tree '{name}': {data}")
                    test_tree_browser.interface_event(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print("WebSocket connection closed with exception %s" % ws.exception())

        return ws

    async def make_app():
        middleware = aiohttp_session.session_middleware(
            aiohttp_session.cookie_storage.EncryptedCookieStorage(
                cryptography.fernet.Fernet.generate_key().decode(), max_age=auth_duration
            )
        )
        # middleware = aiohttp_session.session_middleware(aiohttp_session.SimpleCookieStorage())
        app = web.Application(middlewares=[middleware])

        app.add_routes(
            [
                web.get("/_ws", websocket_handler),
                web.get("/_login", login_handler),
                web.post("/_auth", auth_handler),
                web.get("/favicon.ico", static_handler),
            ]
        )

        if static_dir is not None:
            app.add_routes([web.static("/_static", static_dir)])
        if hasattr(test_tree_browsers, "_repr_html_"):
            app.add_routes(
                [web.get("/{topic_path:.*}", topic_handler), web.get("/_ws", websocket_handler)]
            )
        else:
            if static_dir is not None:
                app.add_routes([web.get("/{test_tree}/_static/{file_path:.*}", static_handler)])
            app.add_routes(
                [
                    web.get("/{test_tree}/_ws", websocket_handler),
                    web.get("/{test_tree}", topic_handler),
                    web.get("/{test_tree}/{topic_path:.*}", topic_handler),
                ]
            )

        policy = SessionIdentityPolicy()
        setup_security(app, policy, AdaptiveTestingPolicy())

        return app

    state = {"site": None, "runner": None}

    async def start_server(state, host, port, ssl_crt, ssl_key):
        if ssl_crt is not None:
            import ssl

            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(ssl_crt, ssl_key)
        else:
            ssl_context = None

        app = await make_app()
        state["runner"] = aiohttp.web.AppRunner(app)
        await state["runner"].setup()
        state["site"] = web.TCPSite(state["runner"], host, port, ssl_context=ssl_context)
        await state["site"].start()
        print(f"Server started at http://{host}:{port}")

    async def stop_server(state):
        await state["site"].stop()
        await state["runner"].shutdown()

    # aiohttp.web.run_app(make_app(), port=port)
    loop.run_until_complete(
        start_server(state, host=host, port=port, ssl_crt=ssl_crt, ssl_key=ssl_key)
    )

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(stop_server(state))


class AdaptiveTestingPolicy(AbstractAuthorizationPolicy):
    async def authorized_userid(self, identity):
        """Retrieve authorized user id.
        Return the user_id of the user identified by the identity
        or 'None' if no user exists related to the identity.
        """
        return identity

    async def permits(self, identity, permission, context=None):
        """Check user permissions.
        Return True if the identity is allowed the permission
        in the current context, else return False.
        """
        return identity == "jack" and permission in ("listen",)
