# Visão Geral

O ContagFiscal Pro é um sistema web (Streamlit) para análise, edição e gestão de notas fiscais eletrônicas (NF-e) e notas fiscais de serviço eletrônicas (NFS-e), com foco em produtividade para escritórios contábeis e departamentos fiscais.

Principais capacidades
- Upload em lote de XMLs de NF-e e NFS-e
- Extração automática de metadados de cada nota e itens (NF-e)
- Edição do CFOP por nota ou por item (com seleção em lote de itens via filtro)
- Catálogo de CFOPs centralizado no banco, com cadastro/edição via sidebar
- Preenchimento em massa de Débito/Crédito/Histórico (sem alterar CFOP)
- Geração de ZIP com XMLs alterados (CFOP por item tem prioridade) e PIS/COFINS zerados
- Geração de CSV em layout contábil (Débito/Crédito/Histórico/Data/Valor/Complemento)
- Preferências por fornecedor/empresa (PostgreSQL), reutilizadas a cada pacote

Fluxo de uso resumido
1. Selecionar empresa (ou cadastrar)
2. Upload de um pacote de XMLs (NF-e e/ou NFS-e)
3. Filtrar e selecionar notas
4. Edição de CFOP por item (com filtros e seleção em lote) ou aplicar CFOP único por nota
5. Ajustar Débito/Crédito/Histórico em massa (opcional)
6. Exportar ZIP (XMLs) e/ou CSV

Público-alvo
- Escritórios contábeis, BPO financeiro e áreas fiscais que precisam processar lotes de notas, harmonizar CFOPs e preparar informações para lançamentos contábeis.

