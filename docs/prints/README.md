# Capturas reais da aplicação

Capturadas em **22/10/2026**, com Django em execução em um servidor HTTP local e Microsoft Edge em modo headless. As imagens não são mockups.

| Arquivo | Conteúdo | Resolução |
| --- | --- | --- |
| [01-admin.png](01-admin.png) | Dashboard autenticado do Django Admin | 1440 × 1080 |
| [02-catalogo.png](02-catalogo.png) | Livros, disponibilidade e formulários de empréstimo | 1440 × 1080 |
| [03-emprestimos-atraso.png](03-emprestimos-atraso.png) | Empréstimos ativo, devolvido e atrasado | 1440 × 1080 |
| [04-catalogo-mobile.png](04-catalogo-mobile.png) | Catálogo em largura de celular | 390 × 844 |

O script `scripts/capture_evidence.py` criou uma base SQLite temporária com os dados fictícios do comando de população. Preparou três empréstimos: um com prazo vencido, um ativo e um devolvido. O registro vencido recebeu datas históricas coerentes apenas na base de captura. A sessão administrativa não possui senha utilizável. O banco principal permaneceu com zero empréstimos e todas as cópias disponíveis.

As quatro páginas foram verificadas no navegador por conteúdo esperado e ausência de overflow horizontal. As imagens de empréstimos e celular também foram inspecionadas visualmente. O recorte é o viewport do navegador, portanto a captura de celular mostra a parte inicial da página, que continua verticalmente.

Para reproduzir, na raiz do projeto:

```powershell
.\venv\Scripts\python.exe scripts/capture_evidence.py
```

Requer Node.js 22+ e Edge no caminho padrão do Windows. Não usa pacotes npm. O Edge roda com GPU no processo principal e sem sandbox do próprio navegador para compatibilidade com o ambiente restrito de captura; o alvo é exclusivamente a aplicação local com dados fictícios. O servidor, a sessão, o perfil e a base temporários são encerrados/removidos após a captura.
