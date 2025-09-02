# Solução de Problemas (FAQ)

Sem conexão com o banco
- Verifique variáveis `SUPABASE_*` e `PG_SSLMODE`
- Teste reachability do host/porta do Postgres

Sem CFOP nos combos
- Banco indisponível: sistema usa fallback local
- Cadastre CFOPs na sidebar e recarregue

ZIP vazio
- Verifique se CFOP por item foi definido ou se CFOP da nota está entre os permitidos

CSV com campos vazios
- Confirme preenchimento de Débito/Crédito/Histórico/Data
- Data precisa estar em formato reconhecível para conversão a DD/MM/AAAA

Interface “travada”
- Botões de aplicar CFOP desabilitam durante execução; aguarde o spinner encerrar

