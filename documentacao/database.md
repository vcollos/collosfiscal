# Banco de Dados

Tecnologia: PostgreSQL via SQLAlchemy.

Tabelas
- `empresas`
  - `id` (PK), `cnpj` (único), `nome`, `razao_social`
- `preferencias_fornecedor_empresa`
  - `id` (PK), `empresa_id`, `cnpj_fornecedor`, `tipo_operacao`, `cfop`, `debito`, `credito`, `historico`, `data_nota`, `complemento`
- `cfop_catalog`
  - `id` (PK), `codigo` (único), `categoria`, `nome`, `descricao`
- `emissores_operacoes` (legado — opcional)
  - `cnpj_emissor` (PK), `tipo_operacao`

Catálogo de CFOPs
- Mantém a lista de CFOPs disponíveis nos combos.
- Seed inicial automático quando tabela vazia.
- Edição/cadastro via sidebar do app.

Preferências por Fornecedor/Empresa
- Armazena últimas escolhas por CNPJ emissor para uma `empresa_id` específica.
- Aplicadas automaticamente quando notas do mesmo CNPJ são processadas.

Conexão & SSL
- Variáveis `SUPABASE_*` e `PG_SSLMODE` suportadas em `src/db.py`.

