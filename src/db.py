from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select, insert, update

# Conexão principal
DATABASE_URL = "postgresql+psycopg2://vitorcollos:soeusei22@localhost:5432/collosfiscal"

engine = create_engine(DATABASE_URL)
metadata = MetaData()
metadata.reflect(bind=engine)

# Reflete as tabelas novas
origem_destino_cfop = Table('origem_destino_cfop', metadata, autoload_with=engine)
tipo_operacao_cfop = Table('tipo_operacao_cfop', metadata, autoload_with=engine)
finalidade_cfop = Table('finalidade_cfop', metadata, autoload_with=engine)

# Tabela antiga para salvar tipo operação de fornecedores
emissores_operacoes = Table(
    "emissores_operacoes",
    metadata,
    Column("cnpj_emissor", String(14), primary_key=True),
    Column("tipo_operacao", String(255), nullable=False),
    extend_existing=True
)

# Nova tabela para preferências por empresa e fornecedor
preferencias_fornecedor_empresa = Table(
    "preferencias_fornecedor_empresa",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("empresa_id", String, nullable=False),
    Column("cnpj_fornecedor", String(14), nullable=False),
    Column("tipo_operacao", String(255)),
    Column("cfop", String(10)),
    Column("debito", String(13)),
    Column("credito", String(13)),
    Column("historico", String(9)),
    Column("data_nota", String),
    Column("complemento", String(255)),
    extend_existing=True
)

# Garante criação das tabelas
metadata.create_all(engine)

# 📋 Funções para buscar interpretações

def buscar_origem_destino(digito):
    with engine.connect() as conn:
        stmt = select(origem_destino_cfop.c.descricao).where(origem_destino_cfop.c.codigo == digito)
        result = conn.execute(stmt).fetchone()
        return result[0] if result else "Origem desconhecida"

def buscar_tipo_operacao(digito):
    with engine.connect() as conn:
        stmt = select(tipo_operacao_cfop.c.descricao).where(tipo_operacao_cfop.c.codigo == digito)
        result = conn.execute(stmt).fetchone()
        return result[0] if result else "Tipo de operação desconhecido"

def buscar_finalidade(digitos):
    with engine.connect() as conn:
        stmt = select(finalidade_cfop.c.descricao).where(finalidade_cfop.c.codigo == digitos)
        result = conn.execute(stmt).fetchone()
        return result[0] if result else "Finalidade desconhecida"

def interpretar_cfop_decomposto(cfop):
    if not cfop or len(cfop) != 4:
        return "CFOP inválido"
    origem = buscar_origem_destino(cfop[0])
    tipo = buscar_tipo_operacao(cfop[1])
    finalidade = buscar_finalidade(cfop[2:])
    return f"{origem} / {tipo} / {finalidade} ({cfop})"

# 📋 Funções para emissor antigo

def buscar_tipo_operacao_emissor(cnpj):
    with engine.connect() as conn:
        stmt = select(emissores_operacoes.c.tipo_operacao).where(emissores_operacoes.c.cnpj_emissor == cnpj)
        result = conn.execute(stmt).fetchone()
        if result:
            return result[0]
        return None

def salvar_tipo_operacao_emissor(cnpj, tipo_operacao):
    with engine.connect() as conn:
        existe = buscar_tipo_operacao_emissor(cnpj)
        if existe:
            stmt = update(emissores_operacoes).where(emissores_operacoes.c.cnpj_emissor == cnpj).values(tipo_operacao=tipo_operacao)
        else:
            stmt = insert(emissores_operacoes).values(cnpj_emissor=cnpj, tipo_operacao=tipo_operacao)
        conn.execute(stmt)
        conn.commit()

# 📋 Novas funções para preferências por empresa e fornecedor

def buscar_preferencia_empresa_fornecedor(empresa_id, cnpj_fornecedor):
    with engine.connect() as conn:
        stmt = select(preferencias_fornecedor_empresa).where(
            (preferencias_fornecedor_empresa.c.empresa_id == empresa_id) &
            (preferencias_fornecedor_empresa.c.cnpj_fornecedor == cnpj_fornecedor)
        )
        result = conn.execute(stmt).fetchone()
        if result:
            return dict(result._mapping)
        return None

def salvar_preferencia_empresa_fornecedor(empresa_id, cnpj_fornecedor, tipo_operacao=None, cfop=None, debito=None, credito=None, historico=None, data_nota=None, complemento=None):
    print(f"Salvando preferência: empresa_id={empresa_id}, cnpj_fornecedor={cnpj_fornecedor}, tipo_operacao={tipo_operacao}, data_nota={data_nota}, complemento={complemento}")
    with engine.connect() as conn:
        pref = buscar_preferencia_empresa_fornecedor(empresa_id, cnpj_fornecedor)
        if pref:
            stmt = update(preferencias_fornecedor_empresa).where(
                (preferencias_fornecedor_empresa.c.empresa_id == empresa_id) &
                (preferencias_fornecedor_empresa.c.cnpj_fornecedor == cnpj_fornecedor)
            ).values(
                tipo_operacao=tipo_operacao,
                cfop=cfop,
                debito=debito,
                credito=credito,
                historico=historico,
                data_nota=data_nota,
                complemento=complemento
            )
        else:
            stmt = insert(preferencias_fornecedor_empresa).values(
                empresa_id=empresa_id,
                cnpj_fornecedor=cnpj_fornecedor,
                tipo_operacao=tipo_operacao,
                cfop=cfop,
                debito=debito,
                credito=credito,
                historico=historico,
                data_nota=data_nota,
                complemento=complemento
            )
        conn.execute(stmt)
        conn.commit()
