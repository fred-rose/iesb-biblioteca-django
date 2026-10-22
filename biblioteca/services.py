"""Operações de circulação: sempre alterar empréstimo e estoque na mesma transação."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from .models import Emprestimo, Livro, Membro


class OperacaoInvalida(ValueError):
    pass


@transaction.atomic
def emprestar(livro_id, membro_id):
    # A primeira consulta já é uma escrita condicional. No SQLite, evita a
    # promoção de um bloqueio de leitura e serializa escritores concorrentes.
    alterados = Livro.objects.filter(pk=livro_id, copias_disponiveis__gt=0).update(
        copias_disponiveis=F("copias_disponiveis") - 1,
    )
    if not alterados:
        raise OperacaoInvalida("Livro inexistente ou sem cópias disponíveis.")
    if not Membro.objects.filter(pk=membro_id).exists():
        raise OperacaoInvalida("Membro inexistente.")
    return Emprestimo.objects.create(
        livro_id=livro_id,
        membro_id=membro_id,
        data_prevista_devolucao=timezone.localdate() + timedelta(days=14),
    )


@transaction.atomic
def devolver(emprestimo_id):
    alterados = Emprestimo.objects.filter(
        pk=emprestimo_id, data_devolucao__isnull=True,
        status__in=[Emprestimo.Status.ATIVO, Emprestimo.Status.ATRASADO],
    ).update(data_devolucao=timezone.localdate(), status=Emprestimo.Status.DEVOLVIDO)
    if not alterados:
        raise OperacaoInvalida("Empréstimo inexistente ou já devolvido.")
    emprestimo = Emprestimo.objects.get(pk=emprestimo_id)
    alterados = Livro.objects.filter(
        pk=emprestimo.livro_id, copias_disponiveis__lt=F("copias_totais"),
    ).update(copias_disponiveis=F("copias_disponiveis") + 1)
    if not alterados:
        raise OperacaoInvalida("Estoque inconsistente. A devolução não foi registrada.")
    return emprestimo


def ranking_livros():
    return Livro.objects.annotate(total_emprestimos=Count("emprestimo")).order_by(
        "-total_emprestimos", "titulo", "pk",
    )
