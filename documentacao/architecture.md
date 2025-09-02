# Arquitetura

Camadas
- Apresentação: Streamlit (`app.py`), componentes de edição de tabelas, filtros, ações em massa.
- Negócio: processamento de XML (leitura/extração com `lxml`), aplicação de CFOP por nota/itens, limpeza de PIS/COFINS.
- Persistência: PostgreSQL via SQLAlchemy (`src/db.py`). Catálogo de CFOPs (cfop_catalog) e preferências (por empresa/fornecedor).

Principais módulos
- `app.py`: orquestra o fluxo, UI, filtros, seleção em lote, aplicação de CFOP e exportações.
- `src/xml_reader.py`: extração de cabeçalho e itens de NF-e.
- `src/nfse_reader.py`: extração de dados básicos de NFS-e.
- `src/db.py`: engine + DDL de tabelas e helpers de leitura/gravação.

Pontos-chave
- Processamento em memória (pandas DataFrames) com `st.session_state` para estado entre interações.
- Geração de ZIP com alteração de CFOP por item (prioridade) ou por nota, com PIS/COFINS zerados.
- Catálogo de CFOPs no banco; combos dinâmicos com fallback local quando DB indisponível.

Fluxo de processamento
1) Upload → 2) Extração → 3) UI (edição/seleção) → 4) Aplicação CFOP → 5) Exportações.

Desempenho & Escalabilidade
- Leitura com barra de progresso; operações CPU-bound locais.
- Armazenamento de preferências e catálogo no banco; XMLs tratados somente em memória.

Segurança
- Variáveis sensíveis via env/secrets. Sem chaves no código.
- Sanitização básica de inputs; integração mínima com rede (apenas DB).

