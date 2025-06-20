#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Carrega as variáveis do .env
load_dotenv()

# Define as variáveis do Supabase
os.environ['SUPABASE_HOST'] = 'aws-0-us-east-1.pooler.supabase.com'
os.environ['SUPABASE_PORT'] = '6543'
os.environ['SUPABASE_DB_NAME'] = 'postgres'
os.environ['SUPABASE_USER'] = 'postgres.ddvpxxgdlqwmfugmdnvq'
os.environ['SUPABASE_PASSWORD'] = 'So Eu Sei 22'

try:
    from src.db import engine
    print("✅ Conexão com Supabase estabelecida com sucesso!")
    
    # Testa uma consulta simples
    with engine.connect() as conn:
        result = conn.execute("SELECT 1 as test")
        print("✅ Consulta de teste executada com sucesso!")
        
except Exception as e:
    print(f"❌ Erro na conexão: {e}") 