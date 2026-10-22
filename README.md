# Sistema de Biblioteca — Projeto 2

Projeto da disciplina Construção de Backend do IESB. Implementado sobre a estrutura Django existente, com SQLite e Django ORM. Os documentos do professor não estavam presentes no workspace; a implementação segue os requisitos da missão anexada.

## Ambiente

Validado com Python **3.14.5**, Django **6.1.2**, asgiref 3.12.1, sqlparse 0.6.0 e tzdata 2026.5. O Django instalado exige Python >= 3.12. As dependências estão fixadas em `requirements.txt`.

Todos os comandos abaixo devem ser executados dentro de `biblioteca_projeto`, no PowerShell. O ambiente virtual existente foi preservado.

```powershell
# Apenas em uma nova cópia, se o ambiente virtual ainda não existir:
py -3.14 -m venv venv

.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py popular_biblioteca
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver
```

Abra <http://127.0.0.1:8000/> para o catálogo e <http://127.0.0.1:8000/admin/> para entrar. Nenhum usuário ou senha padrão é criado. O comando `createsuperuser` solicita as credenciais localmente.

Também é possível ativar o ambiente com `.\venv\Scripts\Activate.ps1` e usar `python manage.py ...`. Não é necessário alterar a política de execução do PowerShell para usar diretamente o executável do ambiente.

## Uso e funcionalidades

- **Catálogo público:** título, autor, ISBN, cópias disponíveis e ranking dos cinco livros mais emprestados.
- **Cadastros no Admin:** autores, livros e membros; pesquisa por nome, título e ISBN, filtro por autor e histórico de empréstimos dentro de cada membro.
- **Empréstimos:** após entrar como equipe, escolha um membro no cartão do livro e registre o empréstimo. O prazo é de 14 dias, com redução de uma cópia disponível.
- **Devoluções:** na página Empréstimos, filtre pelo membro e clique em Devolver. A data e o status são atualizados, com incremento de uma cópia uma única vez.
- **Atrasos:** empréstimos não devolvidos com prazo anterior à data local aparecem como Atrasado. No dia do vencimento ainda não estão atrasados. O cálculo ocorre a cada consulta por `esta_atrasado`, sem tarefa diária.
- **Mensagens e estados vazios:** confirmação de operações, falta de estoque, membro inválido, devolução repetida e ausência de registros. Layout adaptável a celulares.

`meus_emprestimos` é a visão da **equipe de circulação**, com seleção de membro; não há conta pessoal vinculada ao model Membro. Somente usuários ativos com `is_staff=True` acessam os dados dos membros e as operações. Para a demonstração, utilize o superusuário criado acima. Cadastre membros no Admin antes de emprestar.

## Modelagem e consistência

`Autor → Livro` usa `related_name='livros'`. ISBN e e-mail são únicos. As chaves estrangeiras usam `PROTECT` para preservar o histórico. As datas opcionais aceitam `null` e `blank`. Os status persistidos são `ATIVO`, `DEVOLVIDO` e `ATRASADO`; a interface e a propriedade calculam o atraso mesmo quando o status persistido ainda é `ATIVO`.

As funções `emprestar()` e `devolver()` em `biblioteca/services.py` são a entrada para alterações de circulação. Cada função usa `transaction.atomic()` e inicia com um `UPDATE` condicional, usando expressões `F()`. O empréstimo exige estoque > 0; a devolução exige ausência de data de devolução. A atualização e a criação do registro são confirmadas juntas ou revertidas juntas. Não se depende de `select_for_update()`, que não fornece bloqueio de linha no SQLite.

O SQLite serializa as escritas; duas conexões não conseguem consumir a mesma cópia nem devolver duas vezes. O timeout de bloqueio é de 20 segundos. Se o banco continuar ocupado, a interface pede nova tentativa, sem confirmar sucesso. Os testes de concorrência usam um banco SQLite em arquivo separado, criado e removido pelo test runner. Não execute duas suítes de testes simultâneas contra esse mesmo arquivo.

O banco impõe estoque não negativo, disponíveis <= total e coerência entre status e data de devolução. `Livro.clean()` também verifica a relação entre estoque e empréstimos pendentes. No Admin, livros novos exigem disponíveis = total; depois do cadastro, os dois campos de estoque ficam somente para leitura. Empréstimos e o inline são somente para consulta. Faça a circulação pela interface para manter a transação. Ajustes de estoque de livros existentes não fazem parte deste projeto.

Escritas diretas via `QuerySet.update()`, `create()` ou SQL não executam `full_clean()` e podem ignorar invariantes entre tabelas. Não use esses caminhos para operações de circulação; as constraints do banco protegem os limites de cada registro, enquanto os serviços mantêm a consistência entre empréstimo e estoque.

## URLs

| Caminho | Método | Acesso e função |
| --- | --- | --- |
| `/` | GET | Catálogo público |
| `/admin/` | GET/POST | Administração autenticada |
| `/livros/<id>/emprestar/` | POST | Equipe; requer CSRF |
| `/emprestimos/` | GET | Equipe; histórico completo |
| `/membros/<id>/emprestimos/` | GET | Equipe; histórico de um membro |
| `/emprestimos/<id>/devolver/` | POST | Equipe; requer CSRF |

## Dados de demonstração

```powershell
.\venv\Scripts\python.exe manage.py popular_biblioteca
```

O comando é atômico e pode ser repetido. Em uma base vazia, cria 3 autores, 5 livros com 3 cópias cada e 3 membros fictícios com e-mails `example.com`. Não cria empréstimos nem usuários de acesso e não redefine estoque ou registros existentes. Os ISBNs são identificadores ilustrativos da demonstração, sem compromisso com uma edição comercial específica.

## Testes e consultas ORM

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test --verbosity 2
.\venv\Scripts\python.exe manage.py showmigrations
.\venv\Scripts\python.exe manage.py migrate --check
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe manage.py shell
```

No shell:

```python
from django.db.models import Count
from biblioteca.models import Autor, Livro, Membro, Emprestimo
from biblioteca.services import emprestar, devolver, ranking_livros

# Relacionamento reverso
Autor.objects.first().livros.all()

# Empréstimos de um membro
membro = Membro.objects.first()
Emprestimo.objects.filter(membro=membro).select_related("livro")

# Ranking com annotate() e Count(); inclui o histórico devolvido
Livro.objects.annotate(total_emprestimos=Count("emprestimo")).order_by("-total_emprestimos", "titulo", "pk")
list(ranking_livros().values("titulo", "total_emprestimos"))

# Operações seguras (alteram o banco local)
livro = Livro.objects.filter(copias_disponiveis__gt=0).first()
registro = emprestar(livro.pk, membro.pk)
devolver(registro.pk)
```

A suíte cobre cadastros, relacionamentos, unicidade, constraints, prazo, estoque zero, rollback, devolução repetida, datas locais, ranking, filtros, templates, mensagens, permissões, CSRF, Admin, população idempotente e concorrência entre conexões. Consulte [a evidência de execução](docs/validacao.txt) e [o relatório de entrega](docs/relatorio-entrega.md).

## Configuração e segurança

O desenvolvimento usa `DEBUG=True`, host local e fuso `America/Sao_Paulo`. A chave original de desenvolvimento foi removida do código; uma nova chave aleatória é mantida apenas no arquivo local `.django-secret-key`, ignorado pelo Git. Senhas usam o mecanismo de autenticação do Django; operações exigem POST e CSRF. O catálogo não publica nomes nem e-mails de membros.

As variáveis `DJANGO_DEBUG`, `DJANGO_SECRET_KEY` e `DJANGO_ALLOWED_HOSTS` são lidas do ambiente do processo. Arquivos `.env` **não são carregados automaticamente**. Com `DJANGO_DEBUG=false`, a chave deve ser fornecida externamente; caso contrário, a inicialização falha. Uma publicação em produção exigiria configuração própria de HTTPS, cookies seguros, servidor WSGI/ASGI, arquivos estáticos e hosts. O `runserver` atende à demonstração local solicitada.

## Evidências visuais

A pasta [docs/prints](docs/prints/) contém as capturas disponíveis e seu procedimento. Para repetir a captura automatizada, requer Node.js 22+ e Microsoft Edge instalado no caminho padrão do Windows, além do ambiente Python do projeto:

```powershell
.\venv\Scripts\python.exe scripts/capture_evidence.py
```

O script executa a aplicação Django real, incluindo seus arquivos estáticos, em um servidor HTTP local temporário. Cria uma base SQLite isolada dentro do projeto, popula dados fictícios e abre uma sessão administrativa temporária sem senha utilizável. Um empréstimo com prazo vencido é preparado apenas nessa base para demonstrar o indicador. A base e o perfil de navegador são removidos ao terminar. `db.sqlite3` não é usado nem alterado pela captura. Node/Edge são ferramentas opcionais para evidências e não dependências da aplicação.

## Git e publicação

O repositório local está preparado dentro de `biblioteca_projeto`. `.gitignore` exclui o ambiente virtual, bancos, caches, arquivos `.env`, chave local e segredos. Nenhum commit, remoto ou push é criado automaticamente. As migrations e os arquivos de entrega devem ser versionados; o banco é reproduzido por `migrate` e `popular_biblioteca`.

Revise com `git status --short` e `git status --short --ignored`. Antes de publicar, autentique o GitHub CLI com `gh auth login`, defina o repositório de destino e revise os arquivos. O push depende de autorização explícita do responsável.
