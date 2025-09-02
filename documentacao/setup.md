# Instalação & Setup

Pré‑requisitos
- Python 3.10+
- PostgreSQL acessível (local ou hospedado)

Instalação
1. Crie um virtualenv e instale as dependências:
   - `pip install -r requirements.txt`
2. Configure variáveis de ambiente (ou `.env`), por exemplo:
   - `SUPABASE_HOST`, `SUPABASE_PORT`, `SUPABASE_DB_NAME`, `SUPABASE_USER`, `SUPABASE_PASSWORD`
   - Opcional: `PG_SSLMODE=require`
3. Execute o app: `streamlit run app.py`

Configuração de Banco
- O app cria automaticamente as tabelas necessárias ao iniciar (`src/db.py`).
- Catálogo de CFOPs é semeado com valores padrão quando vazio; pode ser editado via sidebar.

Execução
- Acesse a URL do Streamlit (padrão: http://localhost:8501).

