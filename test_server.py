"""Testes do servidor (python -m unittest -v). Sem dependências externas."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server

PRO_LIBERADO = False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.opener = urllib.request.build_opener(NoRedirect)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path, method="GET"):
        request = urllib.request.Request(self.base + path, method=method)
        try:
            with self.opener.open(request) as response:
                return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), error.read().decode("utf-8", "replace")

    def test_health(self):
        status, _, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_paginas_principais(self):
        for path in ["/", "/planos", "/conta", "/pagamentos", "/treinador"]:
            status, headers, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn("text/html", headers["Content-Type"])
            self.assertIn("<title>", body)
            self.assertNotIn("{{", body, path)

    def test_noindex_em_conta_e_pagamentos(self):
        for path in ["/conta", "/pagamentos"]:
            _, headers, body = self.get(path)
            self.assertIn("noindex", headers["X-Robots-Tag"])
            self.assertIn('name="robots"', body)
        _, headers, _ = self.get("/")
        self.assertNotIn("X-Robots-Tag", headers)

    def test_404_com_status_correto(self):
        status, _, body = self.get("/nao-existe")
        self.assertEqual(status, 404)
        self.assertIn("Página não encontrada", body)

    def test_ferramentas_gratis(self):
        for path in ["/gratis/index.html", "/gratis/style.css", "/gratis/app.js", "/gratis/img/logo-cousner.png"]:
            self.assertEqual(self.get(path)[0], 200, path)
        self.assertEqual(self.get("/gratis")[0], 302)
        self.assertEqual(self.get("/favicon.ico")[0], 200)

    def test_assets_do_site(self):
        self.assertEqual(self.get("/static/site.css")[0], 200)
        self.assertEqual(self.get("/static/site.js")[0], 200)

    def test_bloqueia_path_traversal(self):
        for path in ["/gratis/../../server.py", "/gratis/%2e%2e/%2e%2e/server.py",
                     "/static/../server.py", "/paid/pro/../server.py", "/paid/pro/%2e%2e/server.py"]:
            status, _, body = self.get(path)
            self.assertNotEqual(status, 200, path)
            self.assertNotIn("class Handler", body, path)

    def test_metodos_nao_permitidos(self):
        request = urllib.request.Request(self.base + "/", method="POST", data=b"x")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.opener.open(request)
        self.assertEqual(ctx.exception.code, 405)

    def test_head_sem_corpo(self):
        status, _, body = self.get("/", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, "")

    def test_treinador_pro(self):
        status, headers, body = self.get("/paid/pro/treinador.html")
        self.assertIn("no-store", headers["Cache-Control"])
        if PRO_LIBERADO:
            self.assertEqual(status, 200)
            self.assertIn('name="cousner-pro-access" content="public-free"', body)
            self.assertEqual(self.get("/paid/pro/treinador-core.js")[0], 200)
            self.assertEqual(self.get("/paid/pro/nao-existe.js")[0], 404)
            self.assertIn("iframe", self.get("/treinador")[2])
        else:
            self.assertEqual(status, 404)
            self.assertEqual(body, "Em breve.")
            self.assertEqual(self.get("/paid/pro/treinador-core.js")[0], 404)
            self.assertNotIn("iframe", self.get("/treinador")[2])
            self.assertIn("chega em breve", self.get("/treinador")[2])


class WsgiTests(unittest.TestCase):
    def call(self, path, method="GET"):
        result = {}
        def start(status, headers):
            result["status"], result["headers"] = status, dict(headers)
        body = b"".join(server.app({"REQUEST_METHOD": method, "PATH_INFO": path}, start))
        return result["status"], result["headers"], body

    def test_vercel_wsgi(self):
        self.assertTrue(self.call("/")[0].startswith("200"))
        self.assertIn(b"Seu dinheiro merece", self.call("/")[2])
        self.assertTrue(self.call("/nada")[0].startswith("404"))
        self.assertTrue(self.call("/gratis/app.js")[0].startswith("200"))
        self.assertTrue(self.call("/gratis/img/logo-cousner.png")[2].startswith(b"\x89PNG"))
        self.assertTrue(self.call("/static/site.css")[0].startswith("200"))
        self.assertTrue(self.call("/", "POST")[0].startswith("405"))
        self.assertFalse(self.call("/gratis/../../server.py")[0].startswith("200"))


if __name__ == "__main__":
    unittest.main()
