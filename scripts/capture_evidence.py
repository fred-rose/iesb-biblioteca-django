r"""Captura a aplicação real em banco isolado. Requer Node.js 22+ e Edge.

Executar na raiz: .\venv\Scripts\python.exe scripts/capture_evidence.py
Não instala dependências, não cria credenciais e não altera db.sqlite3.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Thread
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings


def main():
    # Um diretório temporário dentro do projeto mantém toda escrita no escopo.
    with TemporaryDirectory(prefix=".evidence-", dir=ROOT) as temporary:
        settings.DATABASES["default"]["NAME"] = Path(temporary) / "evidence.sqlite3"
        django.setup()
        from django.contrib.auth import get_user_model
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from django.db import connections
        from django.test import Client
        from django.utils import timezone
        from biblioteca.models import Emprestimo, Livro, Membro
        from biblioteca.services import devolver, emprestar

        call_command("migrate", verbosity=0)
        call_command("popular_biblioteca", verbosity=0)
        equipe = get_user_model().objects.create_superuser(username="equipe-demonstracao")
        # create_superuser sem senha cria senha inutilizável; somente sessão local.
        cliente = Client()
        cliente.force_login(equipe)
        livros = list(Livro.objects.order_by("pk"))
        membros = list(Membro.objects.order_by("pk"))
        atrasado = emprestar(livros[0].pk, membros[0].pk)
        hoje = timezone.localdate()
        Emprestimo.objects.filter(pk=atrasado.pk).update(
            data_emprestimo=hoje - timedelta(days=16),
            data_prevista_devolucao=hoje - timedelta(days=2),
        )
        emprestar(livros[2].pk, membros[1].pk)
        devolvido = emprestar(livros[4].pk, membros[2].pk)
        devolver(devolvido.pk)
        servidor = make_server("127.0.0.1", 0, StaticFilesHandler(get_wsgi_application()))
        thread = Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            payload = {
                "root": str(ROOT), "baseUrl": f"http://127.0.0.1:{servidor.server_port}",
                "session": cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                "sessionName": settings.SESSION_COOKIE_NAME,
                "profile": str(Path(temporary) / "edge-profile"),
            }
            subprocess.run(["node", str(ROOT / "scripts" / "capture_browser.mjs")],
                           input=json.dumps(payload), text=True, check=True, cwd=ROOT)
        finally:
            servidor.shutdown()
            thread.join(timeout=5)
            servidor.server_close()
            connections.close_all()


if __name__ == "__main__":
    main()
