#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

# Este script testa a conexão usando src.db_supabase.engine.
# Não inclua credenciais no código. Para testes locais, configure um arquivo .env
# ou defina variáveis de ambiente antes de executar.
# Se estiver executando no Streamlit Cloud, configure as secrets e o módulo src.db_supabase
# já tentará ler st.secrets quando disponível.

try:
    from src.db_supabase import engine
    from sqlalchemy import text
    print("✅ Usando src.db_supabase.engine - tentando conectar ao banco...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        print("✅ Consulta de teste executada com sucesso! Resultado:", row[0] if row else None)
except Exception as e:
    print(f"❌ Erro na conexão: {e}")
