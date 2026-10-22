# Relatório de entrega — Projeto 2

Data: **22/10/2026**, fuso America/Sao_Paulo. Toda edição de código, documentação e geração de artefatos foi realizada dentro de `biblioteca_projeto`. O ambiente virtual e a estrutura Django originais foram preservados. Não foram utilizados Supabase ou Vercel.

## 1. Arquivos criados e modificados

**Modificados (6):**

- `biblioteca/models.py`: quatro models, relacionamentos, representações, validações, constraints e propriedade de atraso.
- `biblioteca/admin.py`: cadastros, listagens, pesquisa, filtros, inline e proteções de estoque/histórico.
- `biblioteca/views.py`: catálogo, empréstimo, devolução e listagem por membro, com autenticação e mensagens.
- `biblioteca/tests.py`: 41 testes automatizados.
- `config/settings.py`: registro do app, SQLite e banco de testes em arquivo, idioma, fuso, hosts e chave local fora do código.
- `config/urls.py`: inclusão das URLs do aplicativo, preservando o Admin.

**Criados (23):**

- `biblioteca/services.py`, `biblioteca/forms.py`, `biblioteca/urls.py`.
- `biblioteca/migrations/0001_initial.py`.
- `biblioteca/management/__init__.py`, `biblioteca/management/commands/__init__.py`, `biblioteca/management/commands/popular_biblioteca.py`.
- `biblioteca/templates/biblioteca/base.html`, `biblioteca/templates/biblioteca/lista_livros.html`, `biblioteca/templates/biblioteca/meus_emprestimos.html`.
- `biblioteca/static/biblioteca/style.css`.
- `README.md`, `requirements.txt`, `.gitignore`.
- `scripts/capture_evidence.py`, `scripts/capture_browser.mjs`.
- `docs/validacao.txt`, `docs/relatorio-entrega.md`, `docs/prints/README.md`.
- `docs/prints/01-admin.png`, `docs/prints/02-catalogo.png`, `docs/prints/03-emprestimos-atraso.png`, `docs/prints/04-catalogo-mobile.png`.

**Gerados localmente e ignorados pelo Git:** `db.sqlite3`, `.django-secret-key` e caches Python. O Git foi inicializado em `biblioteca_projeto/.git`. A base SQLite de testes e a base/perfil de captura temporários foram removidos pelas respectivas ferramentas após o uso.

## 2. Implementações por etapa

| Etapa | Resultado |
| --- | --- |
| 2 — Modelagem | Autor, Livro, Membro e Emprestimo implementados; migration inicial criada e aplicada; constraints e validações verificadas. |
| 3 — Admin | Listagens, pesquisa, filtro por autor e TabularInline; estoque existente e circulação protegidos contra edição direta. Dashboard autenticado executado e capturado. |
| 4 — Negócio | Empréstimo com prazo de 14 dias e estoque condicional; devolução única; transações e rollback; proteção comprovada entre duas conexões SQLite. Atraso calculado pela data local. |
| 5 — Interface | Quatro views, URLs e templates; catálogo inicial público, equipe autenticada nas operações e no histórico; POST e CSRF; mensagens, estados vazios e layout responsivo. |
| 6 — Testes/ORM | 41 testes aprovados; ranking com annotate/Count validado em teste e Shell; comando idempotente executado duas vezes no banco local. |
| 7 — Entrega | README, dependências fixadas, gitignore, evidências textuais e quatro capturas reais; repositório Git local preparado. |

## 3. Comandos executados

Executados com o Python do ambiente existente (`.\venv\Scripts\python.exe`):

```text
python --version
python -m pip freeze
python manage.py makemigrations biblioteca
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
python manage.py popular_biblioteca             (duas execuções na base principal)
python manage.py showmigrations
python manage.py migrate --check
python -m pip check
python manage.py shell -c "...contagens, estoque e ranking_livros..."
python scripts/capture_evidence.py
```

Também foram executados `git init`, `git status --short`, `git status --short --untracked-files=all`, `git status --short --ignored`, `git check-ignore`, `git remote -v` e `gh auth status`, além da inspeção dos arquivos existentes. Não houve instalação nem atualização de dependências. A saída da validação final, incluindo os comandos exatos, está em [validacao.txt](validacao.txt).

## 4. Testes e falhas restantes

**41 testes aprovados; zero falhas ou erros na suíte.**

Cobertura: 9 testes de models, 13 de circulação e ranking, 12 de interface/segurança, 4 de Admin, 1 de população idempotente e 2 de concorrência SQLite. Os dois testes de concorrência disputam o mesmo registro por conexões independentes e exigem exatamente um sucesso e um bloqueio de negócio.

`check` passou, `makemigrations --check --dry-run` não detectou mudanças, `migrate --check` confirmou ausência de migrations pendentes e `pip check` confirmou compatibilidade das dependências instaladas. A suite utiliza um SQLite separado e não altera os dados de demonstração.

As quatro capturas foram feitas com respostas HTTP 200 da aplicação e arquivos estáticos carregados. O navegador conferiu o conteúdo esperado e a ausência de overflow horizontal em cada viewport. As imagens de empréstimos e de celular foram inspecionadas visualmente.

## 5. Problemas encontrados, causas e soluções

| Problema | Causa | Solução/estado |
| --- | --- | --- |
| App e funcionalidades ausentes | Estrutura inicial com arquivos de exemplo e app fora de INSTALLED_APPS | App registrado e etapas 2 a 7 implementadas sobre a estrutura existente. |
| Possibilidade de inconsistência do estoque | Leituras seguidas de escritas separadas permitem disputas; editar empréstimos no Admin evita o serviço | UPDATE condicional como primeira consulta da transação, expressões F, rollback e Admin somente para leitura na circulação. |
| Chave de desenvolvimento no código inicial | Configuração padrão gerada pelo Django | Chave removida; chave local aleatória persistida em arquivo ignorado; variável externa obrigatória com DEBUG desativado. |
| Datas de atraso dependeriam de atualização manual | Status persistido não muda sozinho com a passagem dos dias | Propriedade usa timezone.localdate; template prioriza data de devolução e atraso calculado. |
| Edge encerrava a automação | Processo de GPU e renderização não funcionava sob as restrições do ambiente | Captura local com GPU no processo principal e sandbox do navegador desativado, apenas para a base fictícia isolada. Quatro capturas concluídas. |
| Saída de stderr formatada incorretamente pelo PowerShell | A primeira gravação do log tratava linhas vazias do runner como RemoteException | Evidência final gravada com subprocess e captura direta de stdout/stderr em UTF-8. |
| Documentos do professor indisponíveis | Não estavam no workspace | Requisitos detalhados da missão foram usados como referência, conforme autorizado. |
| Publicação GitHub indisponível | GitHub CLI reportou token inválido e nenhum destino remoto estava configurado | Entrega local concluída; publicação não executada. |

## 6. Estado do banco

- SQLite principal: `db.sqlite3`, ignorado pelo Git.
- Todas as migrations de admin, auth, biblioteca, contenttypes e sessions aplicadas.
- **3 autores, 5 livros, 3 membros, 0 empréstimos e 0 usuários de autenticação.**
- **15 cópias totais e 15 disponíveis**; cada livro tem 3 cópias.
- Ranking consultado no Shell retorna os cinco títulos com contagem zero, coerente com o banco sem empréstimos. O teste de ranking comprova contagem e ordenação com histórico, incluindo registros devolvidos e títulos sem empréstimos.
- Os três empréstimos das screenshots existiram apenas no banco temporário de captura. Não há usuário/senha de demonstração persistido na base principal.

## 7. Git/GitHub

Repositório local inicializado somente dentro de `biblioteca_projeto`, sem commits e sem remoto. Os arquivos de entrega aparecem como novos no Git, pois não havia repositório anterior. Ambiente virtual, banco, caches, `.env` e chave local foram confirmados como ignorados.

`gh auth status` informou autenticação inválida. Não houve criação de repositório remoto, envio de mensagens, commit ou push. A revisão pode ser feita a partir do inventário acima e dos arquivos locais. A publicação exige autenticação válida, destino definido e autorização explícita do usuário antes do push.

## 8. Pendências reais

Não há pendência de implementação ou falha de teste conhecida dentro dos requisitos locais. Para usar o Admin no banco principal, o responsável precisa criar sua própria conta com `python manage.py createsuperuser`; isso evita uma credencial padrão na entrega. Para publicar, é necessário autenticar o GitHub, definir o destino, revisar/versionar os arquivos e autorizar o push. A aplicação foi preparada e validada para execução local, sem implantação externa.
