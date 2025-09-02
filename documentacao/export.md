# Exportações (XML & CSV)

ZIP de XMLs
- Critérios:
  - Se existir CFOP por item: aplica nos respectivos `det/prod/CFOP`.
  - Caso contrário: aplica CFOP da nota (apenas se estiver na lista de CFOPs permitidos).
- PIS/COFINS: sempre recriados vazios (CST, vBC, pPIS/pCOFINS, vPIS/vCOFINS como strings em branco).
- Resultado: arquivo `notas_alteradas.zip` para download.

CSV Contábil
- Colunas: DEBITO; CREDITO; HISTORICO; DATA; VALOR; COMPLEMENTO
- DATA formatada como DD/MM/AAAA
- VALOR com 2 casas e vírgula decimal
- COMPLEMENTO: `CNPJ - FORNECEDOR - NUMERO_NF`

