# Interface do Usuário (UI)

Navegação principal (app.py)
- Seleção da empresa (com cadastro rápido)
- Upload de XMLs com barra de progresso (NF-e e NFS-e)
- Tabela de notas com filtro por campo e seleção em massa
- Edição por item (com filtros/seleção em lote) e atalhos de aplicação
- Preenchimento em massa de Débito/Crédito/Histórico
- Exportações (ZIP e CSV)

Filtros
- Notas: dropdown de campo (Todos, fornecedor, CNPJ, chave, CFOP da nota, data etc.) e texto de busca
- Itens: dropdown de campo (Todos, produto, fornecedor, chave, CFOP do item, nItem, valor) e texto de busca
- Opção de “Selecionar todos os filtrados” para notas e itens

Edição por item
- Por nota: aplicar CFOP a todos os itens da nota
- Em lote: aplicar CFOP a todos os itens filtrados/selecionados
- Em todas: aplicar CFOP a todos os itens de todas as notas selecionadas
- Desfazer: botão “↩️ Desfazer última aplicação” restaura a aplicação em lote anterior

Catálogo de CFOPs
- Sidebar com seleção de CFOP existente para editar ou cadastro de um novo
- Campos: Código, Categoria, Nome, Descrição

Mensagens e feedback
- Spinners durante aplicações em lote
- Contadores de seleção
- Alertas para filtros vazios

