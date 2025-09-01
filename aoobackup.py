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

        # xml_reader.extrair_dados_xmls retorna df, arquivos_dict, itens_por_chave
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
        for col in ["tipo_operacao", "data_nota", "complemento", "debito", "credito", "historico"]:
            if col not in st.session_state.df_geral.columns:
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

    # Filtro (universal) por texto — busca em todas as colunas
    col1, col2 = st.columns([3, 1])
    
    with col1:
        filtro_texto = st.text_input("🔍 Filtrar fornecedores contendo:", value=st.session_state.filtro_texto)
        st.session_state.filtro_texto = filtro_texto
    
    with col2:
        st.write("")
        st.write("")
        selecionar_todos = st.checkbox("Selecionar todos os filtrados", value=st.session_state.selecionar_todos)
        st.session_state.selecionar_todos = selecionar_todos

    # Aplicar filtro por texto (universal: todas as colunas)
    if filtro_texto:
        base = st.session_state.df_geral.copy()
        texto = filtro_texto.strip().lower()
        try:
            mask = base.apply(
                lambda r: texto in " ".join(
                    ["" if pd.isna(v) else str(v).lower() for v in r.values]
                ),
                axis=1,
            )
            df_filtrado = base[mask].copy()
        except Exception:
            # Fallback: se algo der errado no apply, não filtra
            df_filtrado = base.copy()
        if df_filtrado.empty:
            st.warning(f"Nenhuma linha encontrada contendo '{filtro_texto}' — exibindo todas as notas.")
            df_filtrado = base
        # Garante colunas exigidas pelo editor
        for col in ["debito", "credito", "historico"]:
            if col not in df_filtrado.columns:
                df_filtrado[col] = ""
    else:
        df_filtrado = st.session_state.df_geral.copy()
        # Garante que as colunas Debito, Credito e Historico estejam presentes no df_filtrado
        for col in ["debito", "credito", "historico"]:
            if col not in df_filtrado.columns:
                df_filtrado[col] = ""
    
    # Adiciona coluna de seleção com valor do checkbox selecionar_todos para todas as linhas
    df_filtrado.insert(0, "Selecionar", st.session_state.selecionar_todos)

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
        "1405",  # Tributos - Estaduais e Municipais
        "1403",  # Revenda - Substituição tributária
        "1910",  # Bonificação/Brinde - Doação ou brinde
        "2403",  # Revenda - Para fora do Estado
        "2910",  # Bonificação/Brinde - Outros Estados
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
        
        # Grava no df_geral sempre o código diretamente
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "tipo_operacao"] = tipo_operacao_codigo
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "data_nota"] = data_nota
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "complemento"] = complemento
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "debito"] = debito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "credito"] = credito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "historico"] = historico
    
    st.divider()

    # Edição de CFOP por item (para as notas selecionadas)
    notas_selecionadas = st.session_state.df_geral[st.session_state.df_geral["chave"].isin(st.session_state.selected_rows)]
    if not notas_selecionadas.empty:
        st.subheader("🔧 Editar CFOP por item (somente notas selecionadas)")
        for _, nota in notas_selecionadas.iterrows():
            chave = nota["chave"]
            fornecedor = nota.get("fornecedor", "")
            itens = st.session_state.itens_por_chave.get(chave, [])
            if not itens:
                continue
            if chave not in st.session_state.item_cfops:
                st.session_state.item_cfops[chave] = {}
            with st.expander(f"Itens da nota {chave} - {fornecedor}", expanded=False):
                # Aplicar CFOP único para todos os itens desta nota
                col_n1, col_n2 = st.columns([2, 1])
                with col_n1:
                    cfop_para_todos = st.selectbox(
                        f"CFOP único para todos os itens da nota {chave}",
                        [""] + CFOP_CODES,
                        index=0,
                        key=f"{chave}_cfop_todos_itens"
                    )
                with col_n2:
                    aplicar_todos_btn = st.button(
                        "Aplicar a todos os itens desta nota",
                        key=f"{chave}_aplicar_todos"
                    )
                if aplicar_todos_btn and cfop_para_todos:
                    count_local = 0
                    for item in itens:
                        nItem = str(item.get("nItem", ""))
                        st.session_state.item_cfops[chave][nItem] = cfop_para_todos
                        count_local += 1
                    st.success(f"Aplicado CFOP '{cfop_para_todos}' em {count_local} item(ns) da nota {chave}")
                for item in itens:
                    nItem = item.get("nItem", "")
                    xProd = item.get("xProd", "")
                    vProd = item.get("vProd", "0")
                    current = (
                        st.session_state.item_cfops[chave].get(nItem)
                        or item.get("cfop")
                        or nota.get("tipo_operacao")
                        or ""
                    )
                    cfop_selecionado = st.selectbox(
                        label=f"CFOP item {nItem} - {xProd} (Valor: {vProd})",
                        options=[""] + CFOP_CODES,
                        index=([""] + CFOP_CODES).index(current) if current in CFOP_CODES else 0,
                        key=f"{chave}_{nItem}_cfop_item"
                    )
                    st.session_state.item_cfops[chave][nItem] = cfop_selecionado

        # Seleção em lote de itens e aplicação de CFOP único
        itens_rows = []
        for _, nota in notas_selecionadas.iterrows():
            chave = nota["chave"]
            fornecedor = nota.get("fornecedor", "")
            itens = st.session_state.itens_por_chave.get(chave, [])
            for item in itens:
                nItem = str(item.get("nItem", ""))
                atual = (
                    st.session_state.item_cfops.get(chave, {}).get(nItem)
                    or item.get("cfop")
                    or nota.get("tipo_operacao")
                    or ""
                )
                itens_rows.append({
                    "Selecionar": False,
                    "chave": chave,
                    "nItem": nItem,
                    "fornecedor": fornecedor,
                    "xProd": item.get("xProd", ""),
                    "vProd": item.get("vProd", ""),
                    "cfop_atual": atual,
                })

        if itens_rows:
            st.caption("Selecione itens por filtro e aplique um CFOP único em lote")
            import pandas as pd  # já importado; redundante, mas seguro
            df_itens = pd.DataFrame(itens_rows)

            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            with col_f1:
                filtro_itens = st.text_input(
                    "Filtrar itens por texto (produto, fornecedor, chave, CFOP, item)",
                    value=st.session_state.get("filtro_itens", ""),
                    key="filtro_itens",
                    placeholder="Ex.: teclado; ACME; 1102; CHAVE..."
                )
            with col_f2:
                itens_select_all = st.checkbox("Selecionar todos os filtrados", value=False, key="itens_select_all")
            with col_f3:
                st.write("")
                st.write("")
                st.write("")

            # Aplica filtro universal por texto em todas as colunas
            df_filtrado = df_itens.copy()
            if filtro_itens:
                texto = filtro_itens.strip().lower()
                try:
                    mask = df_itens.apply(
                        lambda r: texto in " ".join([str(v).lower() for v in r.values if v is not None]),
                        axis=1,
                    )
                    df_filtrado = df_itens[mask].copy()
                except Exception:
                    df_filtrado = df_itens.copy()
                if df_filtrado.empty:
                    st.info("Nenhum item encontrado com o filtro informado; exibindo todos.")
                    df_filtrado = df_itens.copy()

            # Marcar todos os filtrados se solicitado
            if itens_select_all and not df_filtrado.empty:
                df_filtrado["Selecionar"] = True

            edited_items_df = st.data_editor(
                df_filtrado,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", width="small"),
                    "chave": st.column_config.TextColumn("Chave", disabled=True, width="small"),
                    "nItem": st.column_config.TextColumn("Item", disabled=True, width="small"),
                    "fornecedor": st.column_config.TextColumn("Fornecedor", disabled=True),
                    "xProd": st.column_config.TextColumn("Produto", disabled=True),
                    "vProd": st.column_config.TextColumn("Valor", disabled=True, width="small"),
                    "cfop_atual": st.column_config.TextColumn("CFOP atual", disabled=True, width="small"),
                },
                hide_index=True,
                height=380,
                use_container_width=True,
                num_rows="fixed",
                key="data_editor_itens"
            )

            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                novo_cfop_itens = st.selectbox("CFOP para aplicar nos itens selecionados:", [""] + CFOP_CODES, index=0, key="novo_cfop_itens")
            with col_b2:
                aplicar_cfop_itens_btn = st.button("Aplicar CFOP aos itens selecionados")

            if aplicar_cfop_itens_btn:
                # Seleciona os itens marcados; se 'selecionar todos' estiver ativo e nenhum marcado manualmente,
                # aplica em todos os itens do conjunto filtrado atual
                selected_items = edited_items_df[edited_items_df["Selecionar"] == True]
                if itens_select_all and selected_items.empty:
                    selected_items = edited_items_df
                if novo_cfop_itens:
                    count = 0
                    for _, row_it in selected_items.iterrows():
                        chave = row_it["chave"]
                        nItem = str(row_it["nItem"])
                        if chave not in st.session_state.item_cfops:
                            st.session_state.item_cfops[chave] = {}
                        st.session_state.item_cfops[chave][nItem] = novo_cfop_itens
                        count += 1
                    st.success(f"CFOP '{novo_cfop_itens}' aplicado em {count} item(ns)")
                else:
                    st.warning("Selecione um CFOP para aplicar em lote.")
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
            "1405",  # Tributos - Estaduais e Municipais
            "1403",  # Revenda - Substituição tributária
            "1910",  # Bonificação/Brinde - Doação ou brinde
            "2403",  # Revenda - Para fora do Estado
            "2910",  # Bonificação/Brinde - Outros Estados
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

    # Gerar e exportar ZIP com XMLs: aplica CFOP por item quando definido; caso contrário, aplica CFOP da nota
    def gerar_zip_com_xmls_alterados():
        allowed_cfops = {"1102", "2102", "1910", "2910", "1403", "2403", "1405", "1911"}

        # Decide quais notas processar: notas com CFOP permitido no nível da nota
        # ou notas que tenham pelo menos um item com CFOP definido
        chaves_cfop_permitido = set(
            st.session_state.df_geral[
                st.session_state.df_geral["tipo_operacao"].isin(allowed_cfops)
            ]["chave"].tolist()
        )
        chaves_com_itens_editados = set()
        for chave, itens_map in st.session_state.item_cfops.items():
            if any(v for v in itens_map.values()):
                chaves_com_itens_editados.add(chave)

        chaves_por_processar = chaves_cfop_permitido.union(chaves_com_itens_editados)
        if not chaves_por_processar:
            st.warning("Nenhuma nota elegível para gerar XML (verifique CFOP da nota ou CFOP por item).")
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for chave in chaves_por_processar:
                conteudo_xml = st.session_state.arquivos_dict.get(chave) or st.session_state.arquivos_dict.get(f"{chave}.xml")
                if not conteudo_xml:
                    continue

                try:
                    tree = etree.parse(io.BytesIO(conteudo_xml))
                    root = tree.getroot()
                    # Mapeamentos de CFOP por item
                    itens_map = st.session_state.item_cfops.get(chave, {})
                    nota_cfop = (
                        st.session_state.df_geral.loc[
                            st.session_state.df_geral["chave"] == chave, "tipo_operacao"
                        ].values[0]
                        if not st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave].empty
                        else ""
                    )

                    # Se houver CFOP por item, aplica por det; caso contrário, aplica CFOP da nota
                    if any(v for v in itens_map.values()):
                        for det in root.findall(".//{http://www.portalfiscal.inf.br/nfe}det"):
                            nItem_attr = det.get("nItem", "")
                            prod = det.find("{http://www.portalfiscal.inf.br/nfe}prod")
                            if prod is None:
                                continue
                            alvo_cfop = itens_map.get(nItem_attr) or (nota_cfop if nota_cfop in allowed_cfops else None)
                            if not alvo_cfop:
                                continue
                            cfop_elem = prod.find("{http://www.portalfiscal.inf.br/nfe}CFOP")
                            if cfop_elem is None:
                                cfop_elem = etree.SubElement(prod, "{http://www.portalfiscal.inf.br/nfe}CFOP")
                            cfop_elem.text = alvo_cfop
                    else:
                        if nota_cfop in allowed_cfops:
                            for cfop in root.findall(".//{http://www.portalfiscal.inf.br/nfe}CFOP"):
                                cfop.text = nota_cfop
                        else:
                            # Nem CFOP por item, nem CFOP de nota permitido
                            continue

                    # Limpa PIS/COFINS conforme padrão do editor
                    for pis in root.findall(".//{http://www.portalfiscal.inf.br/nfe}PIS"):
                        for child in list(pis):
                            pis.remove(child)
                        pis_aliq = etree.SubElement(pis, "{http://www.portalfiscal.inf.br/nfe}PISAliq")
                        etree.SubElement(pis_aliq, "{http://www.portalfiscal.inf.br/nfe}CST").text = ""
                        etree.SubElement(pis_aliq, "{http://www.portalfiscal.inf.br/nfe}vBC").text = ""
                        etree.SubElement(pis_aliq, "{http://www.portalfiscal.inf.br/nfe}pPIS").text = ""
                        etree.SubElement(pis_aliq, "{http://www.portalfiscal.inf.br/nfe}vPIS").text = ""

                    for cofins in root.findall(".//{http://www.portalfiscal.inf.br/nfe}COFINS"):
                        for child in list(cofins):
                            cofins.remove(child)
                        cofins_aliq = etree.SubElement(cofins, "{http://www.portalfiscal.inf.br/nfe}COFINSAliq")
                        etree.SubElement(cofins_aliq, "{http://www.portalfiscal.inf.br/nfe}CST").text = ""
                        etree.SubElement(cofins_aliq, "{http://www.portalfiscal.inf.br/nfe}vBC").text = ""
                        etree.SubElement(cofins_aliq, "{http://www.portalfiscal.inf.br/nfe}pCOFINS").text = ""
                        etree.SubElement(cofins_aliq, "{http://www.portalfiscal.inf.br/nfe}vCOFINS").text = ""

                    buffer = io.BytesIO()
                    tree.write(buffer, encoding="utf-8", xml_declaration=True, pretty_print=False)
                    nome_arquivo = chave if str(chave).endswith(".xml") else f"{chave}.xml"
                    zipf.writestr(nome_arquivo, buffer.getvalue())
                except Exception as e:
                    print(f"Erro ao processar {chave}: {e}")
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
