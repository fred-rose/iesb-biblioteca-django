from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MembroForm
from .models import Emprestimo, Livro, Membro
from .services import OperacaoInvalida, devolver, emprestar, ranking_livros


def lista_livros(request):
    return render(request, "biblioteca/lista_livros.html", {
        "livros": Livro.objects.select_related("autor").order_by("titulo"),
        "form": MembroForm() if request.user.is_active and request.user.is_staff else None,
        "ranking": ranking_livros()[:5],
    })


@require_POST
@staff_member_required
def emprestar_livro(request, livro_id):
    form = MembroForm(request.POST)
    if form.is_valid():
        try:
            emprestar(livro_id, form.cleaned_data["membro"].pk)
        except OperacaoInvalida as exc:
            messages.error(request, str(exc))
        except OperationalError:
            messages.error(request, "Banco ocupado. Tente novamente em instantes.")
        else:
            messages.success(request, "Empréstimo registrado. Prazo de devolução: 14 dias.")
    else:
        messages.error(request, "Selecione um membro válido.")
    return redirect("biblioteca:lista_livros")


@require_POST
@staff_member_required
def devolver_livro(request, emprestimo_id):
    try:
        emprestimo = devolver(emprestimo_id)
    except OperacaoInvalida as exc:
        messages.error(request, str(exc))
    except OperationalError:
        messages.error(request, "Banco ocupado. Tente novamente em instantes.")
    else:
        messages.success(request, "Devolução registrada com sucesso.")
        return redirect("biblioteca:meus_emprestimos_membro", membro_id=emprestimo.membro_id)
    return redirect("biblioteca:meus_emprestimos")


@staff_member_required
def meus_emprestimos(request, membro_id=None):
    membro = get_object_or_404(Membro, pk=membro_id) if membro_id else None
    emprestimos = Emprestimo.objects.select_related("livro", "membro").order_by("-data_emprestimo", "-pk")
    if membro:
        emprestimos = emprestimos.filter(membro=membro)
    return render(request, "biblioteca/meus_emprestimos.html", {
        "emprestimos": emprestimos, "membro": membro,
        "membros": Membro.objects.order_by("nome", "pk"),
    })
