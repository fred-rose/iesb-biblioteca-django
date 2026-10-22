from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, OperationalError, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Autor, Emprestimo, Livro, Membro
from .services import OperacaoInvalida, devolver, emprestar, ranking_livros


def criar_acervo():
    autor = Autor.objects.create(nome="Autora de teste", nacionalidade="Brasileira")
    livro = Livro.objects.create(titulo="Livro de teste", autor=autor, isbn="TESTE-1",
                                 copias_totais=1, copias_disponiveis=1)
    membro = Membro.objects.create(nome="Leitora", email="leitora@example.com")
    return autor, livro, membro


class ModelosTest(TestCase):
    def setUp(self):
        self.autor, self.livro, self.membro = criar_acervo()

    def test_cadastro_e_representacoes(self):
        self.assertEqual(str(self.autor), "Autora de teste")
        self.assertIsNone(self.autor.data_nascimento)
        self.assertEqual(str(self.livro), "Livro de teste")
        self.assertEqual(str(self.membro), "Leitora")
        self.assertEqual(self.membro.data_cadastro, timezone.localdate())
        self.autor.full_clean()
        self.livro.full_clean()
        self.membro.full_clean()

    def test_relacionamento_autor_livros(self):
        self.assertEqual(list(self.autor.livros.all()), [self.livro])

    def test_isbn_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Livro.objects.create(titulo="Outro", autor=self.autor, isbn=self.livro.isbn,
                                 copias_totais=1, copias_disponiveis=1)

    def test_email_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membro.objects.create(nome="Outra", email=self.membro.email)

    def test_validacao_disponiveis_maior_que_total(self):
        self.livro.copias_disponiveis = 2
        with self.assertRaises(ValidationError):
            self.livro.full_clean()

    def test_banco_bloqueia_disponiveis_maior_que_total(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Livro.objects.filter(pk=self.livro.pk).update(copias_disponiveis=2)

    def test_banco_bloqueia_estoque_negativo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Livro.objects.filter(pk=self.livro.pk).update(copias_disponiveis=-1)

    def test_validacao_estoque_considera_pendentes(self):
        emprestar(self.livro.pk, self.membro.pk)
        self.livro.refresh_from_db()
        self.livro.full_clean()
        self.livro.copias_disponiveis = 1
        with self.assertRaises(ValidationError):
            self.livro.full_clean()

    def test_historico_protegido_contra_exclusao_em_cascata(self):
        emprestar(self.livro.pk, self.membro.pk)
        for obj in (self.autor, self.livro, self.membro):
            with self.assertRaises(ProtectedError):
                obj.delete()


class CirculacaoTest(TestCase):
    def setUp(self):
        self.autor, self.livro, self.membro = criar_acervo()

    def test_emprestimo_ativo_com_estoque_e_prazo(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        self.livro.refresh_from_db()
        self.assertEqual(registro.status, Emprestimo.Status.ATIVO)
        self.assertEqual(registro.data_emprestimo, timezone.localdate())
        self.assertEqual(registro.data_prevista_devolucao, registro.data_emprestimo + timedelta(days=14))
        self.assertEqual(self.livro.copias_disponiveis, 0)
        self.assertEqual(registro.livro, self.livro)
        self.assertEqual(registro.membro, self.membro)
        self.assertIn(self.membro.nome, str(registro))
        self.assertIn(self.livro.titulo, str(registro))

    def test_bloqueio_estoque_zero(self):
        emprestar(self.livro.pk, self.membro.pk)
        with self.assertRaises(OperacaoInvalida):
            emprestar(self.livro.pk, self.membro.pk)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 0)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_livro_inexistente(self):
        with self.assertRaises(OperacaoInvalida):
            emprestar(999999, self.membro.pk)
        self.assertFalse(Emprestimo.objects.exists())

    def test_membro_inexistente_reverte_estoque(self):
        with self.assertRaises(OperacaoInvalida):
            emprestar(self.livro.pk, 999999)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 1)

    def test_falha_na_criacao_reverte_estoque(self):
        with patch("biblioteca.services.Emprestimo.objects.create", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                emprestar(self.livro.pk, self.membro.pk)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 1)
        self.assertFalse(Emprestimo.objects.exists())

    def test_devolucao_atualiza_data_status_e_estoque(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        devolver(registro.pk)
        registro.refresh_from_db()
        self.livro.refresh_from_db()
        self.assertEqual(registro.status, Emprestimo.Status.DEVOLVIDO)
        self.assertEqual(registro.data_devolucao, timezone.localdate())
        self.assertEqual(self.livro.copias_disponiveis, 1)

    def test_devolucao_duplicada(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        devolver(registro.pk)
        with self.assertRaises(OperacaoInvalida):
            devolver(registro.pk)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 1)

    def test_devolucao_inexistente(self):
        with self.assertRaises(OperacaoInvalida):
            devolver(999999)

    def test_falha_estoque_reverte_devolucao(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        # Simula corrupção por escrita ORM direta fora dos serviços.
        Livro.objects.filter(pk=self.livro.pk).update(copias_disponiveis=1)
        with self.assertRaises(OperacaoInvalida):
            devolver(registro.pk)
        registro.refresh_from_db()
        self.assertEqual(registro.status, Emprestimo.Status.ATIVO)
        self.assertIsNone(registro.data_devolucao)

    def test_atraso_usa_data_local_e_ignora_devolvidos(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        with patch("biblioteca.models.timezone.localdate", return_value=date(2026, 10, 22)):
            registro.data_prevista_devolucao = date(2026, 10, 21)
            self.assertTrue(registro.esta_atrasado)
            registro.data_devolucao = date(2026, 10, 22)
            self.assertFalse(registro.esta_atrasado)
            registro.data_devolucao = None
            registro.data_prevista_devolucao = date(2026, 10, 22)
            self.assertFalse(registro.esta_atrasado)
            registro.data_prevista_devolucao = date(2026, 10, 23)
            self.assertFalse(registro.esta_atrasado)

    def test_devolve_status_atrasado_tambem(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        Emprestimo.objects.filter(pk=registro.pk).update(status=Emprestimo.Status.ATRASADO)
        self.assertEqual(devolver(registro.pk).status, Emprestimo.Status.DEVOLVIDO)

    def test_banco_bloqueia_status_incoerente(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Emprestimo.objects.filter(pk=registro.pk).update(status=Emprestimo.Status.DEVOLVIDO)

    def test_ranking_count_inclui_devolvidos_e_livros_sem_emprestimos(self):
        outro = Livro.objects.create(titulo="Outro", autor=self.autor, isbn="TESTE-2",
                                     copias_totais=2, copias_disponiveis=2)
        registro = emprestar(self.livro.pk, self.membro.pk)
        devolver(registro.pk)
        emprestar(self.livro.pk, self.membro.pk)
        ranking = list(ranking_livros())
        self.assertEqual([(l.pk, l.total_emprestimos) for l in ranking], [(self.livro.pk, 2), (outro.pk, 0)])


class InterfaceTest(TestCase):
    def setUp(self):
        self.autor, self.livro, self.membro = criar_acervo()
        self.equipe = get_user_model().objects.create_user(username="equipe", is_staff=True)
        self.client.force_login(self.equipe)
        self.emprestar_url = reverse("biblioteca:emprestar_livro", args=[self.livro.pk])

    def test_catalogo_publico_e_sem_dados_de_membros(self):
        self.client.logout()
        resposta = self.client.get(reverse("biblioteca:lista_livros"))
        self.assertContains(resposta, self.livro.titulo)
        self.assertNotContains(resposta, self.membro.nome)
        self.assertNotContains(resposta, self.membro.email)

    def test_catalogo_autenticado_renderiza_formulario(self):
        resposta = self.client.get(reverse("biblioteca:lista_livros"))
        self.assertContains(resposta, 'name="csrfmiddlewaretoken"')
        self.assertContains(resposta, self.membro.nome)

    def test_estados_vazios(self):
        Livro.objects.all().delete()
        self.assertContains(self.client.get(reverse("biblioteca:lista_livros")), "Nenhum livro cadastrado")
        self.assertContains(self.client.get(reverse("biblioteca:meus_emprestimos")), "Nenhum empréstimo encontrado")

    def test_get_nao_modifica_dados(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        for url in (self.emprestar_url, reverse("biblioteca:devolver_livro", args=[registro.pk])):
            self.assertEqual(self.client.get(url).status_code, 405)
        registro.refresh_from_db()
        self.livro.refresh_from_db()
        self.assertIsNone(registro.data_devolucao)
        self.assertEqual(self.livro.copias_disponiveis, 0)

    def test_post_anonimo_e_usuario_sem_permissao_bloqueados(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        urls = (self.emprestar_url, reverse("biblioteca:devolver_livro", args=[registro.pk]),
                reverse("biblioteca:meus_emprestimos"))
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.post(url, {"membro": self.membro.pk}).status_code, 302)
        usuario = get_user_model().objects.create_user(username="comum")
        self.client.force_login(usuario)
        for url in urls:
            self.assertEqual(self.client.post(url, {"membro": self.membro.pk}).status_code, 302)
        registro.refresh_from_db()
        self.assertIsNone(registro.data_devolucao)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_csrf_obrigatorio_nas_duas_operacoes(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.equipe)
        registro = emprestar(self.livro.pk, self.membro.pk)
        for url in (self.emprestar_url, reverse("biblioteca:devolver_livro", args=[registro.pk])):
            self.assertEqual(cliente.post(url, {"membro": self.membro.pk}).status_code, 403)
        registro.refresh_from_db()
        self.assertIsNone(registro.data_devolucao)

    def test_fluxo_post_com_csrf_real(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.equipe)
        cliente.get(reverse("biblioteca:lista_livros"))
        token = cliente.cookies["csrftoken"].value
        resposta = cliente.post(self.emprestar_url, {"membro": self.membro.pk, "csrfmiddlewaretoken": token}, follow=True)
        self.assertContains(resposta, "Empréstimo registrado")
        registro = Emprestimo.objects.get()
        resposta = cliente.post(reverse("biblioteca:devolver_livro", args=[registro.pk]),
                                {"csrfmiddlewaretoken": token}, follow=True)
        self.assertContains(resposta, "Devolução registrada")
        self.assertContains(resposta, "Devolvido")

    def test_membro_invalido_exibe_mensagem(self):
        resposta = self.client.post(self.emprestar_url, {"membro": "invalido"}, follow=True)
        self.assertContains(resposta, "Selecione um membro válido")
        self.assertFalse(Emprestimo.objects.exists())

    def test_estoque_zero_exibe_mensagem(self):
        emprestar(self.livro.pk, self.membro.pk)
        resposta = self.client.post(self.emprestar_url, {"membro": self.membro.pk}, follow=True)
        self.assertContains(resposta, "sem cópias disponíveis")
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_devolucao_duplicada_exibe_mensagem(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        url = reverse("biblioteca:devolver_livro", args=[registro.pk])
        self.client.post(url)
        self.assertContains(self.client.post(url, follow=True), "já devolvido")

    def test_listagem_filtra_membro_e_exibe_atraso(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        Emprestimo.objects.filter(pk=registro.pk).update(data_prevista_devolucao=timezone.localdate() - timedelta(days=1))
        outro = Membro.objects.create(nome="Outro membro", email="outro@example.com")
        url = reverse("biblioteca:meus_emprestimos_membro", args=[self.membro.pk])
        resposta = self.client.get(url)
        self.assertContains(resposta, "Atrasado")
        self.assertEqual(list(resposta.context["emprestimos"]), [registro])
        resposta = self.client.get(reverse("biblioteca:meus_emprestimos_membro", args=[outro.pk]))
        self.assertEqual(list(resposta.context["emprestimos"]), [])
        self.assertEqual(self.client.get(reverse("biblioteca:meus_emprestimos_membro", args=[999999])).status_code, 404)

    def test_banco_ocupado_exibe_mensagem_sem_sucesso(self):
        with patch("biblioteca.views.emprestar", side_effect=OperationalError):
            resposta = self.client.post(self.emprestar_url, {"membro": self.membro.pk}, follow=True)
        self.assertContains(resposta, "Banco ocupado")
        self.assertFalse(Emprestimo.objects.exists())


class AdminTest(TestCase):
    def setUp(self):
        self.autor, self.livro, self.membro = criar_acervo()
        self.admin = get_user_model().objects.create_superuser(username="admin", email="admin@example.com")
        self.client.force_login(self.admin)

    def test_admin_listagens_e_inline_funcionam(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        for modelo in ("autor", "livro", "membro", "emprestimo"):
            self.assertEqual(self.client.get(reverse(f"admin:biblioteca_{modelo}_changelist")).status_code, 200)
        resposta = self.client.get(reverse("admin:biblioteca_membro_change", args=[self.membro.pk]))
        self.assertContains(resposta, registro.livro.titulo)
        self.assertNotContains(resposta, 'name="emprestimo_set-0-DELETE"')

    def test_admin_bloqueia_manipulacao_estoque(self):
        emprestar(self.livro.pk, self.membro.pk)
        self.client.post(reverse("admin:biblioteca_livro_change", args=[self.livro.pk]), {
            "titulo": self.livro.titulo, "autor": self.autor.pk, "isbn": self.livro.isbn,
            "copias_totais": 99, "copias_disponiveis": 99, "_save": "Salvar",
        })
        self.livro.refresh_from_db()
        self.assertEqual((self.livro.copias_totais, self.livro.copias_disponiveis), (1, 0))

    def test_admin_bloqueia_livro_novo_com_estoque_incompleto(self):
        resposta = self.client.post(reverse("admin:biblioteca_livro_add"), {
            "titulo": "Novo", "autor": self.autor.pk, "isbn": "NOVO",
            "copias_totais": 2, "copias_disponiveis": 1, "_save": "Salvar",
        })
        self.assertContains(resposta, "Um livro novo deve ter todas as cópias disponíveis")
        self.assertFalse(Livro.objects.filter(isbn="NOVO").exists())

    def test_admin_bloqueia_criacao_edicao_e_exclusao_emprestimo(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        for url in (reverse("admin:biblioteca_emprestimo_add"),
                    reverse("admin:biblioteca_emprestimo_change", args=[registro.pk]),
                    reverse("admin:biblioteca_emprestimo_delete", args=[registro.pk])):
            self.assertEqual(self.client.post(url, {"status": "DEVOLVIDO"}).status_code, 403)
        self.assertEqual(Emprestimo.objects.get().status, Emprestimo.Status.ATIVO)


class PopularTest(TestCase):
    def test_comando_idempotente_preserva_estoque(self):
        call_command("popular_biblioteca", stdout=StringIO())
        livro = Livro.objects.first()
        emprestar(livro.pk, Membro.objects.first().pk)
        call_command("popular_biblioteca", stdout=StringIO())
        self.assertEqual((Autor.objects.count(), Livro.objects.count(), Membro.objects.count()), (3, 5, 3))
        livro.refresh_from_db()
        self.assertEqual(livro.copias_disponiveis, 2)
        self.assertEqual(Emprestimo.objects.count(), 1)


class ConcorrenciaSQLiteTest(TransactionTestCase):
    """Duas conexões independentes disputam uma única cópia no banco em arquivo."""
    def setUp(self):
        self.autor, self.livro, self.membro = criar_acervo()

    def disputar(self, operacao, identificador, membro_id=None):
        barreira = Barrier(2)

        def executar():
            connections.close_all()
            try:
                barreira.wait(timeout=10)
                try:
                    if membro_id is None:
                        operacao(identificador)
                    else:
                        operacao(identificador, membro_id)
                except OperacaoInvalida:
                    return "bloqueado"
                return "sucesso"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: executar(), range(2)))
        self.assertCountEqual(resultados, ["sucesso", "bloqueado"])

    def test_dois_emprestimos_concorrentes_nao_excedem_estoque(self):
        self.disputar(emprestar, self.livro.pk, self.membro.pk)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 0)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_duas_devolucoes_concorrentes_incrementam_so_uma_vez(self):
        registro = emprestar(self.livro.pk, self.membro.pk)
        self.disputar(devolver, registro.pk)
        self.livro.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(self.livro.copias_disponiveis, 1)
        self.assertEqual(registro.status, Emprestimo.Status.DEVOLVIDO)
