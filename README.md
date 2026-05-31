# Freebetar

Dashboard Django para controle de apostas, bancas, metas, movimentacoes, calendario de resultados e analytics.

## Como rodar localmente

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Acesse:

```text
http://127.0.0.1:8000/
```

## Variaveis de ambiente

Copie `.env.example` para `.env` se quiser configurar valores locais.

```text
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
```

## Testes

```powershell
.\.venv\Scripts\python.exe manage.py test dashboard
```
