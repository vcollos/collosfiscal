# CollosFiscal Pro - NF-e e NFSe Inteligente

Sistema inteligente para análise, edição e gestão de notas fiscais eletrônicas (NF-e) e notas fiscais de serviço eletrônicas (NFS-e) em XML, com interface web interativa, filtros avançados, edição em massa e integração com banco de dados PostgreSQL.

---

## Índice

- [Visão Geral](#visão-geral)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Lógica de Funcionamento](#lógica-de-funcionamento)
- [Testes](#testes)
- [Boas Práticas e Calistenia de Objetos](#boas-práticas-e-calistenia-de-objetos)
- [Limitações e Melhorias Futuras](#limitações-e-melhorias-futuras)
- [Licença e Créditos](#licença-e-créditos)

---

## Visão Geral

O CollosFiscal Pro permite importar múltiplos arquivos XML de NF-e e NFS-e, visualizar e filtrar os dados, editar tipos de operação em massa ou individualmente, e salvar preferências por fornecedor (CNPJ) no banco de dados. O sistema interpreta automaticamente o CFOP, sugere operações e permite exportar XMLs editados em lote.

Principais funcionalidades:
- Upload múltiplo de XMLs de NF-e e NFS-e.
- Extração automática de dados relevantes (CNPJ, fornecedor, valor, CFOP, etc).
- Filtros por fornecedor e seleção em massa.
- Edição individual ou em massa do tipo de operação, agora diretamente com códigos CFOP.
- Sugestão automática de CFOP interpretado.
- Persistência de preferências por CNPJ no banco PostgreSQL.
- Exportação de XMLs editados em arquivo ZIP.

---

## Instalação

### Pré-requisitos

- Python 3.8+
- PostgreSQL (rodando localmente ou em servidor)
- [pip](https://pip.pypa.io/en/stable/)

### Instalação das dependências

```bash
pip install -r requirements.txt
```

### Dependências

- streamlit
- pandas
- lxml
- sqlalchemy
- psycopg2-binary
- python-dotenv

---

## Configuração

### Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com, por exemplo:

```
UPLOAD_DIR=./uploads
DEBUG=False
```

### Banco de Dados

O app espera um banco PostgreSQL acessível conforme a string de conexão em `src/db.py`:

```
postgresql+psycopg2://vitorcollos:soeusei22@localhost:5432/collosfiscal
```

**Tabelas esperadas:**
- `origem_destino_cfop` (códigos e descrições de origem/destino)
- `tipo_operacao_cfop` (códigos e descrições de tipo de operação)
- `finalidade_cfop` (códigos e descrições de finalidade)
- `emissores_operacoes` (CNPJ emissor, tipo de operação)
- `preferencias_fornecedor_empresa` (preferências por empresa e fornecedor, incluindo CFOP)

O app cria automaticamente as tabelas necessárias se não existirem.

---

## Uso

### Rodando o app

```bash
streamlit run app.py
```

### Fluxo de uso

1. **Upload de XMLs:** Envie múltiplos arquivos XML de NF-e e NFS-e.
2. **Visualização:** O app exibe uma tabela com os dados extraídos.
3. **Filtros:** Filtre fornecedores por texto.
4. **Seleção em massa:** Selecione todas as notas filtradas para edição em lote.
5. **Edição:** Edite o tipo de operação individualmente (dropdown com códigos CFOP) ou em massa (seleção + aplicar).
6. **Salvar no banco:** Salve as preferências de tipo de operação por CNPJ, armazenando o código CFOP.
7. **Exportação:** Exporte XMLs editados em arquivo ZIP.

---

## Estrutura do Projeto

```
collosfiscal/
│
├── app.py                # Interface principal Streamlit
├── requirements.txt
├── .env
├── README.md
├── assets/               # Recursos estáticos (imagens, etc)
└── src/
    ├── __init__.py
    ├── db.py             # Funções de banco e interpretação de CFOP
    ├── utils.py          # Utilitários e mapa de CFOPs
    ├── xml_reader.py     # Leitura de NF-e XML
    ├── nfse_reader.py    # Leitura de NFS-e XML
    ├── xml_editor.py     # Edição de CFOP em NF-e
    └── nfse_editor.py    # Edição de natureza em NFS-e
```

### Diagrama de dependências

```mermaid
graph TD
    app.py --> src/xml_reader.py
    app.py --> src/nfse_reader.py
    app.py --> src/xml_editor.py
    app.py --> src/nfse_editor.py
    app.py --> src/utils.py
    app.py --> src/db.py
    src/xml_reader.py --> src/utils.py
    src/nfse_reader.py --> src/utils.py
    src/xml_editor.py --> src/utils.py
    src/nfse_editor.py --> src/utils.py
```

---

## Lógica de Funcionamento

- **Leitura de XMLs:** Os módulos `xml_reader.py` e `nfse_reader.py` extraem dados relevantes dos arquivos XML, retornando DataFrames e os conteúdos originais.
- **Edição:** Os módulos `xml_editor.py` e `nfse_editor.py` permitem alterar CFOP (NF-e) ou natureza da operação (NFS-e) e exportar os arquivos modificados em ZIP.
- **Banco de Dados:** O módulo `db.py` interpreta CFOPs, busca e salva preferências de tipo de operação por CNPJ.
- **Interface:** O `app.py` orquestra o fluxo, gerencia o estado da sessão, exibe tabelas editáveis, aplica filtros e integra todas as funcionalidades.

---

## Testes

### Testes manuais sugeridos

- Upload de múltiplos XMLs (NF-e e NFS-e misturados).
- Filtro por fornecedor.
- Edição individual e em massa do tipo de operação (com códigos CFOP).
- Salvamento e persistência das preferências no banco.
- Exportação de XMLs editados (verificar integridade dos arquivos).
- Testar com XMLs inválidos ou corrompidos (o app deve ignorar e seguir).

---

## Boas Práticas e Calistenia de Objetos

- Cada módulo tem responsabilidade única.
- Funções pequenas, focadas e reutilizáveis.
- Sem duplicação de lógica.
- Uso de dicionários e DataFrames para clareza e performance.
- Separação clara entre interface, lógica de negócio e persistência.

---

## Limitações e Melhorias Futuras

- Não valida assinatura digital dos XMLs.
- Não faz upload direto para sistemas de gestão.
- Não possui autenticação de usuários.
- Melhorias possíveis: dashboard de estatísticas, logs detalhados, suporte a outros bancos, deploy em nuvem.

---

## Licença e Créditos

Desenvolvido por Vitor Collos.  
Uso interno e educacional.  
Contribuições e sugestões são bem-vindas!
