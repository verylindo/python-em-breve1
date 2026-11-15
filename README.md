# Cousner — Finanças com clareza

Site feito só com **Python, JavaScript, CSS e HTML**. Sem Node, sem build, sem banco de dados e sem dependências para instalar (usa só a biblioteca padrão do Python 3.10+).

O Treinador Pro está **em breve**: botões desativados e `/paid/pro/` responde 404 "Em breve.".

## Como rodar

```bash
python server.py            # http://localhost:3000
PORT=8080 python server.py  # outra porta
python -m unittest -v       # testes
```

## Estrutura

| Pasta/arquivo | O que é |
| --- | --- |
| `server.py` | Servidor HTTP em Python: rotas, metadados (título, descrição, noindex), 404 e arquivos estáticos |
| `templates/layout.html` | Cabeçalho, rodapé e `<head>` compartilhados |
| `pages/*.html` | Conteúdo de cada página (`/`, `/planos`, `/conta`, `/pagamentos`, `/treinador`, 404) |
| `static/site.css`, `static/site.js` | CSS e JS do site |
| `static/gratis/` | Ferramentas gratuitas (HTML/CSS/JS), servidas em `/gratis/` |
| `pro/` | Treinador Pro (HTML/CSS/JS), servido em `/paid/pro/` quando liberado |

## Publicar no Vercel

O repositório já está pronto: `api/index.py` é o ponto de entrada e `vercel.json` manda todas as rotas para ele. Importe o repositório no Vercel sem build command e sem output directory (Framework Preset: *Other*). Em outras hospedagens, use `python server.py` ou o `Dockerfile`.

## O que foi removido

React, TypeScript, Express, tRPC, Drizzle/MySQL, Stripe e login Manus. Nenhum deles era usado: o Pro é aberto (ou ainda não entregue) e todos os dados do usuário ficam no `localStorage` do navegador.
