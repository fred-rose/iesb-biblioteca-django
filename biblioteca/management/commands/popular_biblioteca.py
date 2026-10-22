from django.core.management.base import BaseCommand
from django.db import transaction

from biblioteca.models import Autor, Livro, Membro


class Command(BaseCommand):
    help = "Cadastra 3 autores, 5 livros e 3 membros fictícios sem duplicar nem redefinir estoque."

    @transaction.atomic
    def handle(self, *args, **options):
        autores = []
        for nome, nacionalidade in [
            ("Machado de Assis", "Brasileira"),
            ("Clarice Lispector", "Brasileira"),
            ("José Saramago", "Portuguesa"),
        ]:
            autor = Autor.objects.filter(nome=nome, nacionalidade=nacionalidade).order_by("pk").first()
            if autor is None:
                autor = Autor.objects.create(nome=nome, nacionalidade=nacionalidade)
            autores.append(autor)
        for titulo, isbn, autor in [
            ("Dom Casmurro", "9788535914849", autores[0]),
            ("Memórias Póstumas de Brás Cubas", "9788535914856", autores[0]),
            ("A Hora da Estrela", "9788535914863", autores[1]),
            ("Perto do Coração Selvagem", "9788535914870", autores[1]),
            ("Ensaio sobre a Cegueira", "9788535914887", autores[2]),
        ]:
            Livro.objects.get_or_create(isbn=isbn, defaults={
                "titulo": titulo, "autor": autor, "copias_totais": 3, "copias_disponiveis": 3,
            })
        for nome, email in [
            ("Ana Silva", "ana@example.com"),
            ("Bruno Costa", "bruno@example.com"),
            ("Carla Souza", "carla@example.com"),
        ]:
            Membro.objects.get_or_create(email=email, defaults={"nome": nome})
        self.stdout.write(self.style.SUCCESS("Dados de demonstração disponíveis: 3 autores, 5 livros e 3 membros (mínimos)."))
