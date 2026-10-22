from django import forms

from .models import Membro


class MembroForm(forms.Form):
    membro = forms.ModelChoiceField(
        queryset=Membro.objects.order_by("nome", "pk"), label="Membro",
        empty_label="Selecione um membro",
    )
