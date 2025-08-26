import streamlit as st
from streamlit import rerun
import pandas as pd
import zipfile
import io
from lxml import etree

from src.xml_reader import extrair_dados_xmls
from src.nfse_reader import extrair_dados_nfses_xmls
from src.xml_editor import alterar_cfops_e_gerar_zip
from src.nfse_editor import alterar_natureza_e_gerar_zip
from src.utils import CFOP_MAP
from src.db import (
    interpretar_cfop_decomposto,
    buscar_tipo_operacao_emissor,
    salvar_tipo_operacao_emissor,
    buscar_preferencia_empresa_fornecedor,
    salvar_preferencia_empresa_fornecedor
)

st.set_page_config(page_title="ContagFiscal Pro - NF-e e NFSe Inteligente", layout="wide")
st.title("🧾 ContagFiscal Pro - NF-e e NFSe Inteligente")

# Inicializa session state para persistir dados entre reruns
if "empresa_selecionada" not in st.session_state:
    st.session_state.empresa_selecionada = None
if "df_geral" not in st.session_state:
    st.session_state.df_geral = None
if "selected_rows" not in st.session_state:
    st.session_state.selected_rows = []
if "filtro_texto" not in st.session_state:
    st.session_state.filtro_texto = ""
if "selecionar_todos" not in st.session_state:
    st.session_state.selecionar_todos = False
if "arquivos_dict" not in st.session_state:
    st.session_state.arquivos_dict = {}
if "itens_por_chave" not in st.session_state:
    st.session_state.itens_por_chave = {}
if "item_cfops" not in st.session_state:
    # estrutura: {chave: {nItem: cfop_str}}
    st.session_state.item_cfops = {}

# Função para cadastrar empresa
def cadastrar_empresa(cnpj, razao_social, nome_fantasia):
    from src.db import engine, Table, MetaData, insert
    metadata = MetaData()
    try:
        metadata.reflect(bind=engine)
        empresas_table = Table('empresas', metadata, autoload_with=engine)
        with engine.connect() as conn:
            stmt = insert(empresas_table).values(cnpj=cnpj, nome=nome_fantasia, razao_social=razao_social)
            conn.execute(stmt)
            conn.commit()
        return True
    except Exception as e:
        st.error("Não foi possível cadastrar empresa: banco indisponível ou credenciais faltando. Detalhe: " + str(e))
        return False

# Seleção da empresa no início da sessão com opção de cadastro
if st.session_state.empresa_selecionada is None:
    from src.db import engine, Table, MetaData
    metadata = MetaData()
    empresas = []
    try:
        # Tenta refletir as tabelas e buscar empresas. Em ambientes sem DB (ex: secrets não configurados)
        # evitamos que a aplicação quebre em tempo de importação — tratamos a falha e seguimos em modo limitado.
        metadata.reflect(bind=engine)
        empresas_table = Table('empresas', metadata, autoload_with=engine)
        with engine.connect() as conn:
            result = conn.execute(empresas_table.select())
            empresas = result.fetchall()
    except Exception as e:
        # Mostra aviso no Streamlit (logs do deploy também terão a stack trace); continua sem quebrar o app.
        st.warning("Banco de dados indisponível ou credenciais não configuradas. Configure SUPABASE_* em Settings/Secrets. (Detalhe: " + str(e) + ")")
        empresas = []
    empresa_options = {row[2]: row[0] for row in empresas} if empresas else {}

    col1, col2 = st.columns([3, 1])
    with col1:
        empresa_nome = st.selectbox("Selecione a empresa", options=[""] + list(empresa_options.keys()))
    with col2:
        if st.button("Cadastrar nova empresa"):
            st.session_state.show_cadastro_empresa = True

    if st.session_state.get("show_cadastro_empresa", False):
        with st.form("form_cadastro_empresa"):
            cnpj = st.text_input("CNPJ", max_chars=14)
            razao_social = st.text_input("Razão Social")
            nome_fantasia = st.text_input("Nome Fantasia")
            submitted = st.form_submit_button("Cadastrar")
            if submitted:
                if cnpj and razao_social and nome_fantasia:
                    if cadastrar_empresa(cnpj, razao_social, nome_fantasia):
                        st.success("Empresa cadastrada com sucesso! Recarregue a página para selecionar.")
                        st.session_state.show_cadastro_empresa = False
                else:
                    st.error("Preencha todos os campos para cadastrar.")

    if empresa_nome:
        st.session_state.empresa_selecionada = empresa_options.get(empresa_nome)
    if st.session_state.empresa_selecionada:
        rerun()
    else:
        st.stop()

# Upload de XMLs
if st.button("🔄 Recarregar dados"):
    st.session_state.df_geral = None
    st.session_state.arquivos_dict = {}
    st.session_state.itens_por_chave = {}
    st.session_state.item_cfops = {}
    rerun()

uploaded_files = st.file_uploader("📂 Envie os arquivos XML das NF-es e NFS-es", type=["xml"], accept_multiple_files=True)

if uploaded_files:
    # Só processa os arquivos se ainda não tiverem sido processados
    if st.session_state.df_geral is None:
        files_copy_1 = []
        files_copy_2 = []
        for file in uploaded_files:
            content = file.read()
            b1 = io.BytesIO(content)
            b1.name = file.name
            files_copy_1.append(b1)

            b2 = io.BytesIO(content)
            b2.name = file.name
            files_copy_2.append(b2)

        # xml_reader.extrair_dados_xmls agora retorna df, arquivos_dict, itens_por_chave
        df_nfe, arquivos_nfe, itens_por_chave = extrair_dados_xmls(files_copy_1)
        df_nfse, arquivos_nfse = extrair_dados_nfses_xmls(files_copy_2)

        st.session_state.df_geral = pd.concat([df_nfe, df_nfse], ignore_index=True)  # Atualizando df_geral no session state

        # Merge dos arquivos e itens
        arquivos_dict = {**(arquivos_nfe or {}), **(arquivos_nfse or {})}
        st.session_state.arquivos_dict = arquivos_dict  # Salva no session state
        st.session_state.itens_por_chave = itens_por_chave or {}

        # Garantir que o número de chaves corresponda ao número de linhas (apenas aviso)
        chaves = list(arquivos_dict.keys())
        if len(chaves) != len(st.session_state.df_geral):
            st.warning(f"Atenção: Número de arquivos ({len(chaves)}) pode não corresponder ao número de notas ({len(st.session_state.df_geral)}). Isso é esperado para NFSe ou se nomes repetirem.")

        # Criar coluna 'chave' única para identificar cada linha com o nome do arquivo original
        # OBS: extrair_dados_xmls já popula 'chave' nas linhas; mantemos consistência usando a coluna existente.
        if "chave" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["chave"] = chaves

        # Garante que as colunas existam
        for col in ["tipo_operacao", "data_nota", "complemento", "debito", "credito", "historico", "explodir"]:
            if col not in st.session_state.df_geral.columns:
                if col == "explodir":
                    st.session_state.df_geral[col] = False
                else:
                    st.session_state.df_geral[col] = ""

        # Aplica preferências salvas no banco para a empresa selecionada
        empresa_id = st.session_state.empresa_selecionada
        for cnpj in st.session_state.df_geral["cnpj_emissor"].unique():
            pref = buscar_preferencia_empresa_fornecedor(empresa_id, cnpj)
            if pref:
                idxs = st.session_state.df_geral.index[st.session_state.df_geral["cnpj_emissor"] == cnpj].tolist()
                for idx in idxs:
                    if "tipo_operacao" in pref and pref["tipo_operacao"]:
                        st.session_state.df_geral.at[idx, "tipo_operacao"] = pref["tipo_operacao"]
                    if "data_nota" in pref and pref["data_nota"]:
                        st.session_state.df_geral.at[idx, "data_nota"] = pref["data_nota"]
                    if "complemento" in pref and pref["complemento"]:
                        st.session_state.df_geral.at[idx, "complemento"] = pref["complemento"]
                    if "debito" in pref and pref["debito"]:
                        st.session_state.df_geral.at[idx, "debito"] = pref["debito"]
                    if "credito" in pref and pref["credito"]:
                        st.session_state.df_geral.at[idx, "credito"] = pref["credito"]
                    if "historico" in pref and pref["historico"]:
                        st.session_state.df_geral.at[idx, "historico"] = pref["historico"]

        if st.session_state.df_geral.empty:
            st.error("Nenhuma nota válida encontrada.")
            st.stop()

    st.subheader("🧾 Tabela de Notas (Filtros + Seleção)")

    # Filtro por texto no fornecedor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        filtro_texto = st.text_input("🔍 Filtrar fornecedores contendo:", value=st.session_state.filtro_texto)
        st.session_state.filtro_texto = filtro_texto
    
    with col2:
        st.write("")
        st.write("")
        selecionar_todos = st.checkbox("Selecionar todos os filtrados", value=st.session_state.selecionar_todos)
        st.session_state.selecionar_todos = selecionar_todos

    # Aplicar filtro por texto
    if filtro_texto:
        df_filtrado = st.session_state.df_geral[st.session_state.df_geral["fornecedor"].str.contains(filtro_texto, case=False, na=False)].copy()
        if df_filtrado.empty:
            st.warning(f"Nenhum fornecedor encontrado contendo '{filtro_texto}'")
            df_filtrado = st.session_state.df_geral.copy()
        else:
            # Garante que as colunas Debito, Credito e Historico estejam presentes no df_filtrado
            for col in ["debito", "credito", "historico", "explodir"]:
                if col not in df_filtrado.columns:
                    df_filtrado[col] = "" if col != "explodir" else False
    else:
        df_filtrado = st.session_state.df_geral.copy()
        # Garante que as colunas Debito, Credito e Historico estejam presentes no df_filtrado
        for col in ["debito", "credito", "historico", "explodir"]:
            if col not in df_filtrado.columns:
                df_filtrado[col] = "" if col != "explodir" else False
    
    # Adiciona coluna de seleção com valor do checkbox selecionar_todos para todas as linhas
    df_filtrado.insert(0, "Selecionar", st.session_state.selecionar_todos)
    # Adiciona coluna Explodir logo após
    df_filtrado.insert(1, "Explodir", df_filtrado.get("explodir", False))

    # Lista de códigos CFOP para seleção direta
    CFOP_CODES = [
        "1102",  # Consumo - Dentro do Estado
        "2102",  # Consumo - Fora do Estado
        "1556",  # Revenda - Dentro do Estado
        "2556",  # Revenda - Fora do Estado
        "1126",  # Ativo Imobilizado - Dentro do Estado
        "2126",  # Ativo Imobilizado - Fora do Estado
        "1551",  # Serviço - Dentro do Estado
        "2551",  # Serviço - Fora do Estado
    ]

    edited_df = st.data_editor(
        df_filtrado,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar",
                help="Selecione as linhas para edição em massa",
                default=False,
                width="small",
            ),
            "Explodir": st.column_config.CheckboxColumn(
                "Explodir",
                help="Marque para explodir itens desta nota e editar CFOP por item",
                default=False,
                width="small",
            ),
            "tipo_operacao": st.column_config.SelectboxColumn(
                "Tipo Operação",
                help="Tipo de operação (CFOP code)",
                width="small",
                options=[""] + CFOP_CODES,
            ),
            "data_nota": st.column_config.TextColumn(
                "Data da Nota",
                help="Data da nota fiscal",
                width="small",
                disabled=False,
            ),
            "complemento": st.column_config.TextColumn(
                "Complemento",
                help="CNPJ + Razão Social + Número da Nota",
                width="medium",
                disabled=False,
            ),
            "debito": st.column_config.TextColumn(
                "Debito",
                help="Débito (13 dígitos)",
                width="small",
                disabled=False,
            ),
            "credito": st.column_config.TextColumn(
                "Credito",
                help="Crédito (13 dígitos)",
                width="small",
                disabled=False,
            ),
            "historico": st.column_config.TextColumn(
                "Historico",
                help="Histórico (9 dígitos)",
                width="small",
                disabled=False,
            ),
        },
        hide_index=True,
        height=600,
        use_container_width=True,
        num_rows="fixed",
        key="data_editor"
    )
    
    # Obter linhas selecionadas
    selected_rows = edited_df[edited_df["Selecionar"] == True]

    # Atualiza a lista de chaves selecionadas no session state
    st.session_state.selected_rows = selected_rows["chave"].tolist()

    # Atualiza o dataframe original com as edições feitas pelo usuário
    for idx, row in edited_df.iterrows():
        chave = row["chave"]
        tipo_operacao_codigo = row["tipo_operacao"]  # já é o código diretamente
        data_nota = row.get("data_nota", "")
        complemento = row.get("complemento", "")
        debito = row.get("debito", "")
        credito = row.get("credito", "")
        historico = row.get("historico", "")
        explodir_flag = row.get("Explodir", False)
        
        # Grava no df_geral sempre o código diretamente
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "tipo_operacao"] = tipo_operacao_codigo
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "data_nota"] = data_nota
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "complemento"] = complemento
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "debito"] = debito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "credito"] = credito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "historico"] = historico
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "explodir"] = explodir_flag
    
    st.divider()

    # Se houver notas marcadas como Explodir, mostrar painel para selecionar CFOP por item
    notas_explodir = st.session_state.df_geral[st.session_state.df_geral["explodir"] == True]
    if not notas_explodir.empty:
        st.subheader("🔧 Itens das notas marcadas para explodir (defina CFOP por item)")
        for _, nota in notas_explodir.iterrows():
            chave = nota["chave"]
            fornecedor = nota.get("fornecedor", "")
            itens = st.session_state.itens_por_chave.get(chave, [])
            if not itens:
                st.info(f"Nota {chave} ({fornecedor}) não possui itens extraídos ou é NFSe.")
                continue

            if chave not in st.session_state.item_cfops:
                st.session_state.item_cfops[chave] = {}

            with st.expander(f"Itens da nota {chave} - {fornecedor}", expanded=False):
                cols = st.columns([1, 4, 1, 2])
                for item in itens:
                    nItem = item.get("nItem", "")
                    xProd = item.get("xProd", "")
                    vProd = item.get("vProd", "0")
                    current = st.session_state.item_cfops[chave].get(nItem) or item.get("cfop") or nota.get("tipo_operacao") or ""
                    # CFOP selection per item
                    cfop_selecionado = st.selectbox(
                        label=f"CFOP item {nItem} - {xProd}",
                        options=[""] + CFOP_CODES,
                        index=([""] + CFOP_CODES).index(current) if current in CFOP_CODES else 0,
                        key=f"{chave}_{nItem}_cfop"
                    )
                    st.session_state.item_cfops[chave][nItem] = cfop_selecionado
                    # display product info inline
                    cols[1].write(f"{xProd}")
                    cols[2].write(f"Qtd: {item.get('qCom', '')}")
                    cols[3].write(f"Valor: {vProd}")

    # Tabela combinada: mantém a linha da nota e insere as linhas dos itens logo abaixo (nota + sublinhas)
    # Monta um DataFrame com linhas de nota e linhas de item para edição inline
    combined_rows = []
    for _, nota in st.session_state.df_geral.iterrows():
        chave = nota["chave"]
        # Linha da nota (tipo 'nota')
        combined_rows.append({
            "row_type": "nota",
            "chave": chave,
            "Selecionar": False,
            "Explodir": bool(nota.get("explodir", False)),
            "tipo_operacao": nota.get("tipo_operacao", ""),
            "data_nota": nota.get("data_nota", ""),
            "complemento": nota.get("complemento", ""),
            "debito": nota.get("debito", ""),
            "credito": nota.get("credito", ""),
            "historico": nota.get("historico", ""),
            "fornecedor": nota.get("fornecedor", ""),
            "cnpj_emissor": nota.get("cnpj_emissor", ""),
            "display": f"NOTA: {nota.get('fornecedor','')} - {chave}"
        })
        # Se a nota estiver marcada para explodir, adiciona linhas dos itens logo abaixo (tipo 'item')
        if bool(nota.get("explodir", False)):
            itens = st.session_state.itens_por_chave.get(chave, [])
            for item in itens:
                nItem = item.get("nItem", "")
                combined_rows.append({
                    "row_type": "item",
                    "parent_chave": chave,
                    "nItem": nItem,
                    "chave": chave,
                    "Selecionar": False,
                    "Explodir": True,
                    "tipo_operacao": st.session_state.item_cfops.get(chave, {}).get(nItem, item.get("cfop") or ""),
                    "data_nota": nota.get("data_nota", ""),
                    "complemento": f"ITEM {nItem} - {item.get('xProd','')}",
                    "debito": "",
                    "credito": "",
                    "historico": "",
                    "fornecedor": f"  ↳ {item.get('xProd','')}",
                    "cnpj_emissor": "",
                    "display": f"  ITEM {nItem}: {item.get('xProd','')}"
                })

    combined_df = pd.DataFrame(combined_rows)
    if not combined_df.empty:
        st.subheader("🧾 Notas + Itens (linhas dos itens aparecem abaixo da nota)")
        # Exibe o editor com as linhas combinadas
        edited_combined = st.data_editor(
            combined_df.drop(columns=["row_type", "parent_chave", "nItem"], errors="ignore"),
            column_config={
                "Selecionar": st.column_config.CheckboxColumn(
                    "Selecionar",
                    help="Selecione a nota (aplica apenas a notas)",
                    default=False,
                    width="small",
                ),
                "Explodir": st.column_config.CheckboxColumn(
                    "Explodir",
                    help="Indicador se a nota foi explodida (itens visíveis)",
                    default=False,
                    width="small",
                ),
                "tipo_operacao": st.column_config.SelectboxColumn(
                    "Tipo Operação",
                    help="Tipo de operação (CFOP code). Para itens, será aplicado ao item específico",
                    width="small",
                    options=[""] + CFOP_CODES,
                ),
                "data_nota": st.column_config.TextColumn(
                    "Data da Nota",
                    help="Data da nota fiscal",
                    width="small",
                    disabled=False,
                ),
                "complemento": st.column_config.TextColumn(
                    "Complemento",
                    help="Complemento da nota ou descrição do item",
                    width="medium",
                    disabled=False,
                ),
                "debito": st.column_config.TextColumn(
                    "Debito",
                    help="Débito (13 dígitos)",
                    width="small",
                    disabled=False,
                ),
                "credito": st.column_config.TextColumn(
                    "Credito",
                    help="Crédito (13 dígitos)",
                    width="small",
                    disabled=False,
                ),
                "historico": st.column_config.TextColumn(
                    "Historico",
                    help="Histórico (9 dígitos)",
                    width="small",
                    disabled=False,
                ),
            },
            hide_index=True,
            height=500,
            use_container_width=True,
            num_rows="fixed",
            key="data_editor_combined"
        )

        # Propaga alterações do editor combinado de volta ao estado
        # Nós precisamos manter o mapeamento entre as linhas exibidas e as linhas origem (nota vs item)
        # Como o data_editor foi passado sem as colunas auxiliares, usamos a mesma ordem das linhas de combined_df
        for i, (_, src_row) in enumerate(combined_df.iterrows()):
            try:
                edited_row = edited_combined.iloc[i]
            except Exception:
                continue

            if src_row.get("row_type") == "nota":
                chave = src_row.get("chave")
                # Atualiza apenas campos do nível da nota
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "tipo_operacao"] = edited_row.get("tipo_operacao", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "data_nota"] = edited_row.get("data_nota", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "complemento"] = edited_row.get("complemento", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "debito"] = edited_row.get("debito", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "credito"] = edited_row.get("credito", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "historico"] = edited_row.get("historico", "")
                st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "explodir"] = bool(edited_row.get("Explodir", False))
            elif src_row.get("row_type") == "item":
                parent = src_row.get("parent_chave")
                nItem = src_row.get("nItem")
                cfop_val = edited_row.get("tipo_operacao", "")
                # Salva CFOP do item no session_state.item_cfops
                if parent:
                    if parent not in st.session_state.item_cfops:
                        st.session_state.item_cfops[parent] = {}
                    st.session_state.item_cfops[parent][str(nItem)] = cfop_val

    else:
        st.info("Nenhuma nota carregada para exibir com itens.")
    # Alterar tipo de operação em massa
    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
    
    with col1:
        novo_tipo = st.selectbox("🚀 Tipo de operação para aplicar nos selecionados:", [
            "1102",  # Consumo - Dentro do Estado
            "2102",  # Consumo - Fora do Estado
            "1556",  # Revenda - Dentro do Estado
            "2556",  # Revenda - Fora do Estado
            "1126",  # Ativo Imobilizado - Dentro do Estado
            "2126",  # Ativo Imobilizado - Fora do Estado
            "1551",  # Serviço - Dentro do Estado
            "2551",  # Serviço - Fora do Estado
            "5152",  # Transferência - Dentro do Estado
            "6152",  # Transferência - Fora do Estado
            "5910",  # Bonificação / Brinde - Dentro do Estado
            "6910",  # Bonificação / Brinde - Fora do Estado
            "5915",  # Doação - Dentro do Estado
            "6915",  # Doação - Fora do Estado
            "5920",  # Demonstração - Dentro do Estado
            "6920",  # Demonstração - Fora do Estado
            "5931",  # Remessa para Conserto - Dentro do Estado
            "6931",  # Remessa para Conserto - seFora do Estado
            "5932",  # Retorno de Conserto - Dentro do Estado
            "6932",  # Retorno de Conserto - Fora do Estado
            "5949",  # Remessa para Industrialização - Dentro do Estado
            "6949",  # Remessa para Industrialização - Fora do Estado
            "5951",  # Retorno de Industrialização - Dentro do Estado
            "6951",  # Retorno de Industrialização - Fora do Estado
        ])
    with col2:
        novo_debito = st.text_input("Débito (13 dígitos)", max_chars=13)
    with col3:
        novo_credito = st.text_input("Crédito (13 dígitos)", max_chars=13)
    with col4:
        novo_historico = st.text_input("Histórico (9 dígitos)", max_chars=9)
    with col5:
        aplicar_btn = st.button("✅ Aplicar novo tipo e valores para selecionados", use_container_width=True)

    if aplicar_btn:
        if st.session_state.df_geral is not None:
            if not selected_rows.empty:
                cfop_code = novo_tipo  # já é o código diretamente
                # Guarda as chaves das linhas selecionadas
                chaves_selecionadas = selected_rows["chave"].tolist()
                
                # Atualiza o dataframe no session state com o código CFOP
                for chave in chaves_selecionadas:
                    idxs = st.session_state.df_geral.index[st.session_state.df_geral["chave"] == chave].tolist()
                    for idx in idxs:
                        if cfop_code:
                            st.session_state.df_geral.at[idx, "tipo_operacao"] = cfop_code
                        if novo_debito:
                            st.session_state.df_geral.at[idx, "debito"] = novo_debito
                        if novo_credito:
                            st.session_state.df_geral.at[idx, "credito"] = novo_credito
                        if novo_historico:
                            st.session_state.df_geral.at[idx, "historico"] = novo_historico
                
                st.success(f"Alterado tipo de operação e valores para {len(selected_rows)} notas selecionadas!")
                
                # Força rerun para atualizar a interface
                rerun()
            else:
                st.warning("Nenhuma nota selecionada.")

    st.divider()

    # Salvar tipos no banco
    if st.button("💾 Salvar tipos no Banco"):
        empresa_id = st.session_state.empresa_selecionada
        if empresa_id is None:
            st.error("Nenhuma empresa selecionada para salvar.")
        else:
            for idx, row in st.session_state.df_geral.iterrows():
                cnpj = row["cnpj_emissor"]
                cfop_code = row["tipo_operacao"]
                data_nota = row.get("data_nota", "")
                complemento = row.get("complemento", "")
                debito = row.get("debito", "")
                credito = row.get("credito", "")
                historico = row.get("historico", "")
                if cnpj and cfop_code:
                    st.write(f"Salvando: empresa_id={empresa_id}, cnpj={cnpj}, tipo_operacao={cfop_code}, data_nota={data_nota}, complemento={complemento}")
                    salvar_preferencia_empresa_fornecedor(
                        empresa_id,
                        cnpj,
                        tipo_operacao=cfop_code,
                        cfop=None,
                        data_nota=data_nota,
                        complemento=complemento,
                        debito=debito,
                        credito=credito,
                        historico=historico
                    )
            st.success("Preferências salvas no banco.")

    # Gerar e exportar ZIP com XMLs alterados
    def gerar_zip_com_xmls_alterados():
        NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
        allowed_cfops = {"1102", "2102", "1910", "2910", "1403", "2403", "1911"}

        # Pega todas as chaves onde tipo_operacao está entre os CFOPs permitidos OR que foram explodidas com items com CFOPs
        chaves_por_processar = []

        # Notas com CFOP válido no nível da nota
        chaves_por_processar.extend(
            st.session_state.df_geral[
                st.session_state.df_geral["tipo_operacao"].isin(allowed_cfops)
            ]["chave"].tolist()
        )

        # Notas explodidas com item CFOPs definidos
        for chave, itens_map in st.session_state.item_cfops.items():
            if any(v for v in itens_map.values()):
                if chave not in chaves_por_processar:
                    chaves_por_processar.append(chave)

        if not chaves_por_processar:
            st.warning("Nenhuma nota com CFOP permitido ou itens explodidos com CFOP definido para gerar XML.")
            return None

        arquivos_filtrados = {}
        for chave in chaves_por_processar:
            # Pega o conteúdo original do XML
            conteudo_xml = st.session_state.arquivos_dict.get(chave) or st.session_state.arquivos_dict.get(chave + ".xml")
            if not conteudo_xml:
                continue

            # Decide se a nota é explodida
            explodida = bool(st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "explodir"].values[0])

            if explodida:
                # Usará as escolhas em st.session_state.item_cfops[chave]
                itens = st.session_state.itens_por_chave.get(chave, [])
                itens_map = st.session_state.item_cfops.get(chave, {})
                # Agrupa itens por CFOP escolhido
                grupos = {}
                for item in itens:
                    nItem = item.get("nItem", "")
                    cfop_selecionado = itens_map.get(nItem) or item.get("cfop") or st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "tipo_operacao"].values[0]
                    if not cfop_selecionado:
                        continue
                    grupos.setdefault(cfop_selecionado, []).append(item)

                # Para cada grupo, cria um XML separado contendo somente os det correspondentes
                for cfop_val, itens_do_grupo in grupos.items():
                    # Gera nome de arquivo baseado no original + cfop
                    original_name = chave if chave.endswith(".xml") else f"{chave}.xml"
                    nome_saida = f"{original_name.rstrip('.xml')}__{cfop_val}.xml"

                    try:
                        tree = etree.parse(io.BytesIO(conteudo_xml))
                        root = tree.getroot()

                        # Remove dets que não pertencem ao grupo (identificando por nItem)
                        dets = root.findall(".//{http://www.portalfiscal.inf.br/nfe}det")
                        nitems_keep = set([it.get("nItem") for it in itens_do_grupo if it.get("nItem")])
                        for det in dets:
                            nItem_attr = det.get("nItem", "")
                            if nItem_attr not in nitems_keep:
                                parent = det.getparent()
                                parent.remove(det)

                        # Atualiza CFOP em itens mantidos
                        for det in root.findall(".//{http://www.portalfiscal.inf.br/nfe}det"):
                            prod = det.find("{http://www.portalfiscal.inf.br/nfe}prod")
                            if prod is None:
                                continue
                            nItem_attr = det.get("nItem", "")
                            if nItem_attr in nitems_keep:
                                cfop_elem = prod.find("{http://www.portalfiscal.inf.br/nfe}CFOP")
                                if cfop_elem is None:
                                    cfop_elem = etree.SubElement(prod, f"{{{NFE_NAMESPACE}}}CFOP")
                                cfop_elem.text = cfop_val

                        # Recalcula vNF (valor total da nota) como soma dos vProd dos dets mantidos
                        soma = 0.0
                        for prod in root.findall(".//{http://www.portalfiscal.inf.br/nfe}prod"):
                            vProd = prod.findtext("{http://www.portalfiscal.inf.br/nfe}vProd", default="0") or "0"
                            try:
                                soma += float(vProd)
                            except Exception:
                                pass
                        # Atualiza elemento vNF se existir
                        vnf_elem = root.find(".//{http://www.portalfiscal.inf.br/nfe}vNF")
                        if vnf_elem is not None:
                            vnf_elem.text = f"{soma:.2f}"
                        # Também atualizar elementos de totais se necessário (opcional)

                        # Limpa PIS/COFINS como antes
                        for pis in root.findall(".//{http://www.portalfiscal.inf.br/nfe}PIS"):
                            for child in list(pis):
                                pis.remove(child)
                            pis_aliq = etree.SubElement(pis, f"{{{NFE_NAMESPACE}}}PISAliq")
                            etree.SubElement(pis_aliq, f"{{{NFE_NAMESPACE}}}CST").text = ""
                            etree.SubElement(pis_aliq, f"{{{NFE_NAMESPACE}}}vBC").text = ""
                            etree.SubElement(pis_aliq, f"{{{NFE_NAMESPACE}}}pPIS").text = ""
                            etree.SubElement(pis_aliq, f"{{{NFE_NAMESPACE}}}vPIS").text = ""

                        for cofins in root.findall(".//{http://www.portalfiscal.inf.br/nfe}COFINS"):
                            for child in list(cofins):
                                cofins.remove(child)
                            cofins_aliq = etree.SubElement(cofins, f"{{{NFE_NAMESPACE}}}COFINSAliq")
                            etree.SubElement(cofins_aliq, f"{{{NFE_NAMESPACE}}}CST").text = ""
                            etree.SubElement(cofins_aliq, f"{{{NFE_NAMESPACE}}}vBC").text = ""
                            etree.SubElement(cofins_aliq, f"{{{NFE_NAMESPACE}}}pCOFINS").text = ""
                            etree.SubElement(cofins_aliq, f"{{{NFE_NAMESPACE}}}vCOFINS").text = ""

                        buffer = io.BytesIO()
                        tree.write(buffer, encoding="utf-8", xml_declaration=True, pretty_print=False)
                        arquivos_filtrados[nome_saida] = (buffer.getvalue(), cfop_val)
                    except Exception as e:
                        print(f"Erro ao processar explodida {chave} grupo {cfop_val}: {e}")
                        continue

            else:
                # Não explodida: pega o cfop no nível da nota (se estiver entre allowed_cfops)
                novo_cfop = st.session_state.df_geral.loc[
                    st.session_state.df_geral["chave"] == chave,
                    "tipo_operacao"
                ].values[0]
                try:
                    arquivos_filtrados[chave] = (conteudo_xml, novo_cfop)
                except Exception as e:
                    print(f"Erro ao preparar arquivo {chave}: {e}")
                    continue

        if not arquivos_filtrados:
            st.warning("Nenhum arquivo válido para gerar ZIP.")
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for nome_arquivo, (conteudo, cfop) in arquivos_filtrados.items():
                try:
                    # Se já é bytes (do explodido), escrevemos diretamente.
                    if isinstance(conteudo, (bytes, bytearray)):
                        zipf.writestr(nome_arquivo, conteudo)
                    else:
                        # Caso seja objeto io.BytesIO
                        zipf.writestr(nome_arquivo, conteudo)
                except Exception as e:
                    print(f"Erro ao adicionar {nome_arquivo} ao ZIP: {e}")
                    continue
        zip_buffer.seek(0)
        return zip_buffer

    if st.button("📦 Gerar ZIP com XMLs alterados"):
        zip_buffer = gerar_zip_com_xmls_alterados()
        if zip_buffer is None:
            # Se não houver notas/itens para gerar, tenta gerar a partir do df_geral sem alterações
            arquivos_filtrados = {}
            for _, row in st.session_state.df_geral.iterrows():
                chave = row["chave"]
                conteudo_xml = st.session_state.arquivos_dict.get(chave) or st.session_state.arquivos_dict.get(chave + ".xml")
                if conteudo_xml:
                    arquivos_filtrados[f"{chave}.xml"] = (conteudo_xml, None)

            if not arquivos_filtrados:
                st.warning("Nenhuma nota válida para gerar ZIP.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
                    for nome_arquivo, (conteudo, _) in arquivos_filtrados.items():
                        try:
                            zipf.writestr(nome_arquivo, conteudo)
                        except Exception as e:
                            print(f"Erro ao adicionar {nome_arquivo} ao ZIP: {e}")
                            continue
                zip_buffer.seek(0)
                st.download_button(
                    label="⬇️ Baixar ZIP com XMLs originais",
                    data=zip_buffer,
                    file_name="notas_originais.zip",
                    mime="application/zip"
                )
        else:
            st.download_button(
                label="⬇️ Baixar ZIP com XMLs alterados",
                data=zip_buffer,
                file_name="notas_alteradas.zip",
                mime="application/zip"
            )
    # Gerar e exportar CSV com dados selecionados
    if st.button("📄 Gerar CSV com dados selecionados"):
        import tempfile
        from datetime import datetime

        # Definir os cabeçalhos conforme solicitado
        csv_headers = ["DEBITO", "CREDITO", "HISTORICO", "DATA", "VALOR", "COMPLEMENTO"]

        # Filtrar e formatar os dados conforme especificado
        df = st.session_state.df_geral.copy()

        # Filtrar colunas necessárias e renomear para os cabeçalhos
        df_csv = df[["debito", "credito", "historico", "data_nota", "valor_total"]].copy()
        df_csv.columns = csv_headers[:-1]  # Exclui COMPLEMENTO para renomear

        # DATA: formatar para DD/MM/AAAA
        def format_date(date_str):
            try:
                dt = pd.to_datetime(date_str, errors='coerce')
                if pd.isna(dt):
                    return ""
                return dt.strftime("%d/%m/%Y")
            except Exception:
                return ""
        df_csv["DATA"] = df_csv["DATA"].apply(format_date)

        # VALOR: numérico com 2 casas decimais e separador decimal vírgula
        df_csv["VALOR"] = df_csv["VALOR"].apply(lambda x: f"{float(x):.2f}".replace(".", ",") if pd.notnull(x) else "0,00")

        # DEBITO, CREDITO, HISTORICO: manter como string sem preenchimento de zeros
        df_csv["DEBITO"] = df_csv["DEBITO"].astype(str)
        df_csv["CREDITO"] = df_csv["CREDITO"].astype(str)
        df_csv["HISTORICO"] = df_csv["HISTORICO"].astype(str)

        # COMPLEMENTO: concatenar "CNPJ - FORNECEDOR - NUMERO_NOTA" como string única
        def format_complemento(row):
            cnpj = row.get("cnpj_emissor", "")
            fornecedor = row.get("fornecedor", "")
            numero_nota = row.get("nNF", "") or row.get("nnotafiscal", "")
            parts = [cnpj, fornecedor, numero_nota]
            return " - ".join([p for p in parts if p])

        df_csv["COMPLEMENTO"] = df.apply(format_complemento, axis=1)

        # Gerar nome do arquivo com "YYYY/MM" + Nome Fantasia + ".csv"
        nome_fantasia = ""
        if st.session_state.empresa_selecionada:
            from src.db import engine, Table, MetaData
            metadata = MetaData()
            nome_fantasia = ""
            try:
                metadata.reflect(bind=engine)
                empresas_table = Table('empresas', metadata, autoload_with=engine)
                with engine.connect() as conn:
                    result = conn.execute(empresas_table.select().where(empresas_table.c.id == st.session_state.empresa_selecionada))
                    empresa = result.fetchone()
                    if empresa:
                        nome_fantasia = empresa.nome or empresa.razao_social or "empresa"
            except Exception as e:
                st.warning("Não foi possível ler dados da empresa do banco: " + str(e))
                nome_fantasia = "empresa"

        now = datetime.now()
        prefix = now.strftime("%Y/%m")
        filename = f"{prefix}_{nome_fantasia}.csv"

        # Criar arquivo CSV temporário com separador ";"
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, newline='', suffix=".csv") as tmpfile:
            df_csv.to_csv(tmpfile.name, index=False, sep=";")
            tmpfile.seek(0)
            csv_data = tmpfile.read()

        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv"
        )
