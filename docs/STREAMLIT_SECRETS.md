# Configurar Secrets no Streamlit Cloud (para uso com Supabase)

Este documento descreve como configurar as variáveis secretas no Streamlit Cloud para que a aplicação use o Supabase de forma segura. O projeto já contém suporte para ler `st.secrets` (quando rodando no Streamlit) e faz fallback para variáveis de ambiente locais.

---

## 1) O que adicionar no Streamlit Cloud

No painel do seu app em https://share.streamlit.io:

1. Abra o app desejado.
2. Clique em Settings → Secrets.
3. Adicione as credenciais do Supabase no formato TOML.

Opção A — usando seção toml `[supabase]` (recomendado):
```toml
[supabase]
SUPABASE_URL = "sua_url_do_supabase"
SUPABASE_KEY = "sua_chave_publica_do_supabase"
```

Opção B — usando variáveis no nível superior:
```toml
SUPABASE_URL = "sua_url_do_supabase"
SUPABASE_ANON_KEY = "sua_chave_publica_do_supabase"
# ou
SUPABASE_KEY = "sua_chave_publica_do_supabase"
```

Observações:
- `SUPABASE_URL` pode ser a URL do projeto (ex.: https://xxxxx.supabase.co) ou uma URL de conexão Postgres (se você tiver).
- Prefira usar a chave pública (anon/public) para operações do frontend/app. Não use a service_role key em clientes públicos.
- Remova barras extras no final da URL.

---

## 2) Como encontrar suas credenciais no Supabase

1. Acesse o dashboard do Supabase: https://app.supabase.com
2. Selecione seu projeto.
3. Vá em Settings → API.
4. Copie:
   - Project URL → para `SUPABASE_URL`
   - Project API Key (anon/public) → para `SUPABASE_KEY` ou `SUPABASE_ANON_KEY`

---

## 3) Como o código do projeto usa as secrets

O módulo `src/db_supabase.py` já foi atualizado para:

- Tentar importar `streamlit` e ler `st.secrets`.
  - Primeiro tenta a seção `st.secrets["supabase"]["SUPABASE_URL"]` e `["SUPABASE_KEY"]`
  - Depois tenta chaves no nível superior (`SUPABASE_URL`, `SUPABASE_ANON_KEY` ou `SUPABASE_KEY`)
- Se `SUPABASE_URL` for uma connection string que começa com `postgres`, ela será usada diretamente como `DATABASE_URL`.
- Caso contrário, ele monta a connection string a partir das variáveis de ambiente (`SUPABASE_HOST`, `SUPABASE_PASSWORD`, `SUPABASE_DB_NAME`, etc).

Isso permite:
- Rodar localmente com `.env` ou variáveis de ambiente.
- Rodar no Streamlit Cloud usando `st.secrets` sem alterar o código.

---

## 4) Testar a conexão localmente

1. Configure um arquivo `.env` na raiz (ou exporte variáveis de ambiente) com equivalentes:
```
SUPABASE_HOST=...
SUPABASE_PORT=...
SUPABASE_DB_NAME=...
SUPABASE_USER=...
SUPABASE_PASSWORD=...
# ou, opcionalmente:
SUPABASE_URL=postgresql://user:pass@host:port/dbname
```

2. Execute o script de teste:
```bash
python3 test_connection.py
```

Saída esperada em caso de sucesso:
- "✅ Usando src.db_supabase.engine - tentando conectar ao banco..."
- "✅ Consulta de teste executada com sucesso! Resultado: 1"

Em caso de erro, verifique:
- As variáveis definidas no Streamlit secrets (ou `.env`)
- Se a chave usada é a anon/public e não a service_role (em apps públicos)

---

## 5) Verificação no Streamlit Cloud

Depois de configurar as secrets no painel do Streamlit Cloud:

- Faça um deploy/commit no repositório conectado (ou re-run do app no painel).
- No log do app (ou exibindo mensagens com st.write), você deve ver sucesso ao executar a consulta de teste se o app tentar conectar.
- Caso queira verificar manualmente, adicione temporariamente um trecho seguro no app (não exponha chaves) que execute uma consulta de teste curta e imprima um status (o código atual já lança mensagens de erro em caso de falha).

---

## 6) Boas práticas

- Nunca commit suas chaves ou `.env` contendo credenciais no repositório.
- Use `st.secrets` no Streamlit Cloud em vez de variáveis no código.
- Use a chave `anon/public` para o app; reserve `service_role` para operações de backend seguras e não públicas.
- Verifique permissões no Supabase (Row Level Security) conforme necessário.

---

## 7) Onde o projeto já foi alterado

Arquivos relevantes:
- `src/db_supabase.py` — passa a tentar usar `st.secrets` antes do fallback para variáveis de ambiente.
- `test_connection.py` — script de teste atualizado para usar `src.db_supabase.engine`.

---

Se quiser, posso:
- Gerar um snippet para colocar no seu `app.py` mostrando status de conexão (usando st.status/ st.write) para facilitar debug no Streamlit Cloud.
- Ajudar a executar o teste localmente (preciso que confirme se quer que eu rode comandos aqui).
