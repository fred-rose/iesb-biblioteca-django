from django.urls import path

from . import views

app_name = "biblioteca"
urlpatterns = [
    path("", views.lista_livros, name="lista_livros"),
    path("livros/<int:livro_id>/emprestar/", views.emprestar_livro, name="emprestar_livro"),
    path("emprestimos/", views.meus_emprestimos, name="meus_emprestimos"),
    path("membros/<int:membro_id>/emprestimos/", views.meus_emprestimos, name="meus_emprestimos_membro"),
    path("emprestimos/<int:emprestimo_id>/devolver/", views.devolver_livro, name="devolver_livro"),
]
