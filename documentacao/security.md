# Segurança & Operação

Credenciais
- Configure variáveis de ambiente para o banco (sem hardcode no repositório).
- Utilize `PG_SSLMODE=require` quando o provedor exigir TLS (ex.: Supabase).

Permissões
- O app não escreve arquivos fora do processo de download (ZIP/CSV).
- Sem upload persistente de XMLs; processamento em memória reduz superfícies.

Validações
- Campos de texto são tratados como strings; operações críticas (ZIP/CSV) validam entradas.
- XMLs inválidos são ignorados com mensagens no log.

Observabilidade
- Logs no console do Streamlit/servidor.
- Contadores e spinners para feedback ao usuário.

