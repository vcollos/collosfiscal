# Processamento e Edição de Notas

Leitura de XMLs
- NF-e: `src/xml_reader.py` extrai chave (Id), fornecedor, CNPJ emissor, valor total, CFOP atual e lista de itens (nItem, xProd, vProd, CFOP do item).
- NFS-e: `src/nfse_reader.py` extrai número/identificador, fornecedor, CNPJ, valor e data.
- Barras de progresso indicam quantos arquivos foram lidos.

Edição de CFOP
- Por item: o usuário define o CFOP item a item via selectbox.
- Em lote (itens): o usuário filtra/seleciona itens e aplica um CFOP único a todos os itens resultantes.
- Por nota: atalho para aplicar um único CFOP a todos os itens daquela nota.
- Em todas as notas selecionadas: atalho para aplicar um CFOP a todos os itens de todas as notas marcadas.
- Desfazer: reverte a última aplicação em lote (por nota/itens/todas).

Preferências
- O sistema aplica preferências por CNPJ emissor (e empresa) ao carregar um novo pacote, preenchendo campos padrão.

