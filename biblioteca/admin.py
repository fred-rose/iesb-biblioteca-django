from django.contrib import admin
from django import forms

from .models import Autor, Emprestimo, Livro, Membro


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ("nome", "nacionalidade", "data_nascimento")
    search_fields = ("nome", "nacionalidade")


class LivroAdminForm(forms.ModelForm):
    class Meta:
        model = Livro
        fields = "__all__"

    def clean(self):
        dados = super().clean()
        if not self.instance.pk and dados.get("copias_totais") != dados.get("copias_disponiveis"):
            raise forms.ValidationError("Um livro novo deve ter todas as cópias disponíveis.")
        return dados


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    form = LivroAdminForm
    list_display = ("titulo", "autor", "copias_totais", "copias_disponiveis")
    list_filter = ("autor",)
    search_fields = ("titulo", "isbn")
    list_select_related = ("autor",)

    def get_readonly_fields(self, request, obj=None):
        # O estoque existente só é alterado pelos serviços transacionais.
        return ("copias_totais", "copias_disponiveis") if obj else ()


class EmprestimoInline(admin.TabularInline):
    model = Emprestimo
    extra = 0
    can_delete = False
    fields = ("livro", "data_emprestimo", "data_prevista_devolucao", "data_devolucao", "status", "esta_atrasado")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Membro)
class MembroAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "data_cadastro")
    search_fields = ("nome", "email")
    inlines = (EmprestimoInline,)


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ("livro", "membro", "data_prevista_devolucao", "status", "esta_atrasado")
    list_select_related = ("livro", "membro")
    list_filter = ("status",)
    readonly_fields = ("livro", "membro", "data_emprestimo", "data_prevista_devolucao", "data_devolucao", "status", "esta_atrasado")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "Administração da Biblioteca"
admin.site.site_title = "Biblioteca IESB"
