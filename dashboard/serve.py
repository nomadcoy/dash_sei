"""Launcher do dashboard com um service worker de retry para os assets estï¿½ticos.



O tï¿½nel (devtunnel) perde alguns arquivos `/static/*` em rajadas, o que quebra os

chunks JS do Streamlit. Este launcher:

  1. serve `/sw.js` (mesmo domï¿½nio, escopo "/");

  2. injeta o registro do service worker no index.html;

  3. o SW re-tenta baixar e cacheia os /static/* que falharem.



Roda o Streamlit normalmente (inclusive o WebSocket), sem proxy externo.

"""



from __future__ import annotations



import os

import sys

from pathlib import Path



_RAIZ = Path(__file__).resolve().parent.parent

if str(_RAIZ) not in sys.path:

    sys.path.insert(0, str(_RAIZ))



import streamlit.web.server.starlette.starlette_static_routes as _sr

from starlette.responses import FileResponse, Response



_APP = _RAIZ / "dashboard" / "app.py"

_SW = Path(__file__).resolve().parent / "sw.js"



_SW_JS = _SW.read_text(encoding="utf-8")



_INJECT = (
    "<script>(function(){"
    "function loadMods(){document.querySelectorAll('script[type=\"text/gv-module\"]')"
    ".forEach(function(s){var n=document.createElement('script');n.type='module';"
    "if(s.getAttribute('crossorigin')!==null)n.setAttribute('crossorigin','');"
    "n.src=s.getAttribute('src');document.head.appendChild(n);});}"
    "function go(){loadMods();}"
    "if(!('serviceWorker' in navigator)){"
    "document.documentElement.setAttribute('data-sw','unsupported');go();return;}"
    "var t=setTimeout(go,5000);"
    "navigator.serviceWorker.register('/sw.js',{scope:'/'}).then(function(){"
    "document.documentElement.setAttribute('data-sw','registered');"
    "return navigator.serviceWorker.ready;"
    "}).then(function(reg){"
    "document.documentElement.setAttribute('data-sw','ready');"
    "try{if(reg&&reg.active)reg.active.postMessage({type:'precache'});}catch(e){}"
    "if(navigator.serviceWorker.controller){clearTimeout(t);go();}"
    "else{navigator.serviceWorker.addEventListener('controllerchange',"
    "function(){clearTimeout(t);go();},{once:true});}"
    "}).catch(function(){"
    "document.documentElement.setAttribute('data-sw','error');clearTimeout(t);go();});"
    "})();</script>"
)



_orig_create = _sr.create_streamlit_static_handler





def _patched_create(directory: str, base_url: str | None):

    handler = _orig_create(directory, base_url)

    index_path = getattr(handler, "_index_path", os.path.join(directory, "index.html"))

    orig_get = handler.get_response



    async def get_response(path, scope):

        p = (path or "").replace("\\", "/").lstrip("/")

        if p == "sw.js" or p.endswith("/sw.js"):

            return Response(

                content=_SW_JS,

                media_type="application/javascript",

                headers={

                    "Cache-Control": "no-store",

                    "Service-Worker-Allowed": "/",

                },

            )



        resp = await orig_get(path, scope)



        try:

            is_index = isinstance(resp, FileResponse) and os.path.basename(

                str(getattr(resp, "path", ""))

            ) == "index.html"

        except Exception:

            is_index = False



        if is_index:

            html = Path(index_path).read_text(encoding="utf-8")

            html = html.replace('type="module"', 'type="text/gv-module"')

            if "/sw.js" not in html:

                if "</head>" in html:

                    html = html.replace("</head>", _INJECT + "</head>", 1)

                elif "</body>" in html:

                    html = html.replace("</body>", _INJECT + "</body>", 1)

                else:

                    html = html + _INJECT

            return Response(

                content=html,

                media_type="text/html",

                headers={"Cache-Control": "no-store"},

            )



        return resp



    handler.get_response = get_response

    return handler





_sr.create_streamlit_static_handler = _patched_create





def main() -> None:

    from streamlit.web import cli as stcli



    porta = os.environ.get("DASH_PORT", "8599")

    sys.argv = [

        "streamlit",

        "run",

        str(_APP),

        "--server.headless", "true",

        "--server.address", "0.0.0.0",

        "--server.port", porta,

        "--server.fileWatcherType", "none",

        "--browser.gatherUsageStats", "false",

    ]

    sys.exit(stcli.main())





if __name__ == "__main__":

    main()