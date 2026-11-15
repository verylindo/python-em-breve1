#!/usr/bin/env python3
"""Cousner — servidor web em Python puro (somente biblioteca padrão).

Uso:  python server.py      (PORT, HOST e PUBLIC_APP_URL são opcionais)
"""
import html
import json
import mimetypes
import os
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
PAGES_DIR = BASE / "pages"
PRO_DIR = BASE / "pro"
LAYOUT_FILE = BASE / "templates" / "layout.html"

# Decisão do proprietário: não derive este valor de variável de ambiente.
PRO_PUBLIC_FREE = False

NOINDEX = "noindex, nofollow, noarchive"

PAGES = {
    "/": {
        "file": "home.html",
        "title": "Cousner — organize suas finanças com clareza",
        "description": "Ferramentas gratuitas para juros compostos, aposentadoria, gastos, ganhos e metas. Conheça o Treinador Financeiro Cousner Pro.",
    },
    "/planos": {
        "file": "plans.html",
        "title": "Cousner Pro aberto gratuitamente",
        "description": "Use o Treinador Financeiro Cousner Pro sem cadastro, assinatura ou pagamento.",
    },
    "/conta": {
        "file": "account.html",
        "title": "Acesso Cousner — Pro gratuito",
        "description": "O Treinador Financeiro Cousner Pro está aberto sem login ou pagamento.",
        "noindex": True,
    },
    "/pagamentos": {
        "file": "payments.html",
        "title": "Cobranças — Cousner Pro gratuito",
        "description": "O Cousner Pro está aberto sem pagamento ou assinatura.",
        "noindex": True,
    },
    "/treinador": {
        "file": "trainer.html",
        "title": "Treinador Financeiro — Cousner Pro gratuito",
        "description": "Acesse gratuitamente o Treinador Financeiro Cousner Pro, sem cadastro, conta ou pagamento.",
    },
}

NOT_FOUND = {
    "file": "notfound.html",
    "title": "Página não encontrada — Cousner",
    "description": "A página que você procurou não foi encontrada no Cousner.",
    "noindex": True,
    "status": 404,
}

STATIC_ROOT_FILES = {"/favicon.ico", "/favicon.png", "/apple-touch-icon.png"}

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def load_env_file():
    """Lê um arquivo .env simples (CHAVE=valor), sem sobrescrever o ambiente."""
    env = BASE / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def public_origin():
    """Origem https válida em PUBLIC_APP_URL (sem caminho, query ou credenciais) ou None."""
    raw = os.environ.get("PUBLIC_APP_URL", "").strip()
    try:
        url = urlsplit(raw)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            return None
        if url.path not in ("", "/") or url.query or url.fragment:
            return None
        return f"https://{url.netloc}"
    except ValueError:
        return None


def attr(value):
    return html.escape(value, quote=True)


def meta(kind, key, content):
    return f'  <meta {kind}="{key}" content="{attr(content)}" />'


def render_page(route_path, page):
    layout = LAYOUT_FILE.read_text(encoding="utf-8")
    content = (PAGES_DIR / page["file"]).read_text(encoding="utf-8").rstrip()
    extra = []
    if page.get("noindex"):
        extra.append(meta("name", "robots", NOINDEX))
    else:
        origin = public_origin()
        card = "summary_large_image" if origin else "summary"
        extra += [meta("name", "twitter:card", card),
                  meta("name", "twitter:title", page["title"]),
                  meta("name", "twitter:description", page["description"])]
        if origin:
            canonical = f"{origin}{route_path}"
            image = f"{origin}/gratis/img/og-cousner.png"
            extra += [meta("property", "og:url", canonical),
                      meta("property", "og:image", image),
                      meta("name", "twitter:image", image),
                      f'  <link rel="canonical" href="{attr(canonical)}" />']
    values = {
        "title": attr(page["title"]),
        "description": attr(page["description"]),
        "extra_meta": "\n".join(extra),
        "content": content,
        "year": str(datetime.now().year),
    }
    out = layout
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out.encode("utf-8")


def safe_file(root, relative):
    """Devolve o arquivo dentro de root ou None (bloqueia ../ e links para fora)."""
    root = root.resolve()
    try:
        candidate = (root / relative).resolve()
    except (OSError, ValueError):
        return None
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def make_response(status, body=b"", content_type="text/plain; charset=utf-8", headers=None):
    hdrs = {"Content-Type": content_type, "X-Content-Type-Options": "nosniff"}
    hdrs.update(headers or {})
    return status, hdrs, body


def page_response(route_path, page, headers=None):
    hdrs = {"Cache-Control": "no-cache"}
    if page.get("noindex"):
        hdrs["X-Robots-Tag"] = NOINDEX
    hdrs.update(headers or {})
    return make_response(page.get("status", 200), render_page(route_path, page), "text/html; charset=utf-8", hdrs)


def not_found():
    return page_response("/404", NOT_FOUND)


def file_response(path, headers=None):
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
        content_type += "; charset=utf-8"
    hdrs = {"Cache-Control": "public, max-age=3600"}
    hdrs.update(headers or {})
    return make_response(200, path.read_bytes(), content_type, hdrs)


def pro_assets(path):
    headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": NOINDEX}
    if not PRO_PUBLIC_FREE:
        return make_response(404, "Em breve.".encode("utf-8"), headers=headers)
    relative = path[len("/paid/pro"):].lstrip("/") or "treinador.html"
    target = safe_file(PRO_DIR, relative)
    if target is None:
        return make_response(404, "Arquivo não encontrado.".encode("utf-8"), headers=headers)
    if target.suffix.lower() == ".html":
        text = target.read_text(encoding="utf-8")
        if "</head>" not in text:
            return make_response(500, b"", headers=headers)
        marker = '<meta name="cousner-pro-access" content="public-free">\n</head>'
        return make_response(200, text.replace("</head>", marker, 1).encode("utf-8"),
                             "text/html; charset=utf-8", headers)
    return file_response(target, headers)


def route(method, path):
    """Núcleo único do site: recebe método e caminho (já decodificado) e devolve (status, headers, corpo)."""
    if method not in ("GET", "HEAD"):
        return make_response(405, b"", headers={"Allow": "GET, HEAD"})
    normalized = path.rstrip("/") or "/"

    if normalized == "/api/health":
        return make_response(200, json.dumps({"status": "ok"}).encode(), "application/json",
                             {"Cache-Control": "no-store"})
    if normalized in PAGES:
        return page_response(normalized, PAGES[normalized])
    if normalized == "/404":
        return not_found()
    if normalized == "/gratis":
        return make_response(302, b"", headers={"Location": "/gratis/index.html"})
    if normalized == "/paid/pro" or path.startswith("/paid/pro/"):
        return pro_assets(path)
    if path.startswith("/gratis/"):
        target = safe_file(STATIC / "gratis", path[len("/gratis/"):])
        return file_response(target) if target else not_found()
    if path.startswith("/static/"):
        target = safe_file(STATIC, path[len("/static/"):])
        return file_response(target) if target else not_found()
    if path in STATIC_ROOT_FILES:
        target = safe_file(STATIC / "gratis" / "img", path.lstrip("/"))
        return file_response(target) if target else not_found()
    return not_found()


def safe_route(method, path):
    try:
        return route(method, path)
    except Exception as error:  # nunca vaza detalhes internos
        print(f"[erro] {path}: {error}", file=sys.stderr)
        return make_response(500, "Erro interno.".encode("utf-8"))


# ---------- 1) Servidor local / Docker ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "Cousner"
    sys_version = ""

    def handle_any(self):
        status, headers, body = safe_route(self.command, unquote(urlsplit(self.path).path))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = handle_any


# ---------- 2) WSGI (Vercel e qualquer hospedagem com WSGI) ----------
def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/") or "/"
    status, headers, body = safe_route(method, path)
    phrase = HTTPStatus(status).phrase
    out = list(headers.items()) + [("Content-Length", str(len(body)))]
    start_response(f"{status} {phrase}", out)
    return [] if method == "HEAD" else [body]


def main():
    load_env_file()
    try:
        port = int(os.environ.get("PORT", "3000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        sys.exit("PORT inválida (use um número de 1 a 65535).")
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Cousner rodando em http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
