from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Autor(models.Model):
    nome = models.CharField(max_length=150)
    nacionalidade = models.CharField(max_length=80)
    data_nascimento = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.nome


class Livro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.ForeignKey(Autor, on_delete=models.PROTECT, related_name="livros")
    isbn = models.CharField(max_length=20, unique=True)
    copias_totais = models.PositiveIntegerField()
    copias_disponiveis = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(copias_disponiveis__lte=F("copias_totais")),
                name="livro_disponiveis_ate_total",
            ),
        ]

    def clean(self):
        super().clean()
        if (self.copias_disponiveis is not None and self.copias_totais is not None
                and self.copias_disponiveis > self.copias_totais):
            raise ValidationError({"copias_disponiveis": "As cópias disponíveis não podem superar o total."})
        if self.pk and self.copias_totais is not None and self.copias_disponiveis is not None:
            pendentes = self.emprestimo_set.filter(data_devolucao__isnull=True).count()
            if self.copias_totais - self.copias_disponiveis != pendentes:
                raise ValidationError("O estoque deve corresponder aos empréstimos não devolvidos.")

    def __str__(self):
        return self.titulo


class Membro(models.Model):
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    data_cadastro = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Emprestimo(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido"
        ATRASADO = "ATRASADO", "Atrasado"

    livro = models.ForeignKey(Livro, on_delete=models.PROTECT)
    membro = models.ForeignKey(Membro, on_delete=models.PROTECT)
    data_emprestimo = models.DateField(auto_now_add=True)
    data_prevista_devolucao = models.DateField()
    data_devolucao = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(status="DEVOLVIDO", data_devolucao__isnull=False)
                           | Q(status__in=["ATIVO", "ATRASADO"], data_devolucao__isnull=True)),
                name="emprestimo_status_e_devolucao_coerentes",
            ),
        ]

    @property
    def esta_atrasado(self):
        return self.data_devolucao is None and self.data_prevista_devolucao < timezone.localdate()

    def __str__(self):
        return f"{self.membro} — {self.livro}"
