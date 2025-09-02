# Guia Técnico (Contábil)

Objetivo
- Descrever os processos do ContagFiscal Pro na ótica contábil/fiscal: como o sistema classifica, padroniza e prepara informações para escrituração e conciliação.

Processos Principais
- Coleta: importação em lote de XMLs (NF-e/NFS-e) fornecidos pelos clientes/ERPs
- Classificação: definição de CFOP por nota ou por item, conforme a natureza da operação
- Parametrização: preenchimento de contas (Débito/Crédito/Histórico) e datas
- Consolidação: geração de arquivos de trabalho (XMLs ajustados e CSV contábil)

Regras de Negócio (resumo)
- CFOP por item tem prioridade sobre o CFOP da nota na geração dos XMLs
- É possível definir CFOP único para todos os itens de uma nota, ou aplicar em lote por filtros
- PIS/COFINS são zerados nos XMLs gerados, independentemente do CFOP selecionado
- O catálogo de CFOPs é gerenciado pela equipe (via sidebar) e serve de referência para as escolhas
- Preferências por fornecedor/empresa são reaplicadas ao processar novos pacotes

Lançamentos Contábeis (CSV)
- DEBITO: conta débito (13 dígitos)
- CREDITO: conta crédito (13 dígitos)
- HISTORICO: código de histórico (9 dígitos)
- DATA: data do documento (DD/MM/AAAA)
- VALOR: valor monetário, 2 casas decimais, vírgula decimal
- COMPLEMENTO: “CNPJ - RAZÃO SOCIAL - NÚMERO NF”

Boas Práticas
- Definir previamente um conjunto de CFOPs padrão no catálogo e validar com a equipe fiscal
- Processar por lotes homogêneos (mesmo período/empresa) para maior eficiência
- Usar filtros de itens para aplicar CFOPs iguais em produtos similares
- Revisar rapidamente o CSV antes de exportar para o sistema contábil

Auditoria & Rastreabilidade
- As aplicações de CFOP em lote podem ser desfeitas (última aplicação), permitindo correções rápidas
- Preferências gravadas no banco fornecem histórico de parametrizações por fornecedor

