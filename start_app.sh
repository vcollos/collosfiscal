#!/bin/bash

# Define as variáveis do Supabase
export SUPABASE_HOST=aws-0-us-east-1.pooler.supabase.com
export SUPABASE_PORT=6543
export SUPABASE_DB_NAME=postgres
export SUPABASE_USER=postgres.ddvpxxgdlqwmfugmdnvq
export SUPABASE_PASSWORD="So Eu Sei 22"
export APP_ENV=production

# Inicia a aplicação
/home/collos/apps/collosfiscal/venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0 