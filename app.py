import streamlit as st
from streamlit import rerun
import pandas as pd
import zipfile
import io
from lxml import etree

from src.xml_reader import extrair_dados_xmls
from src.nfse_reader import extrair_dados_nfses_xmls
# (Removidos imports não utilizados)
from src.db import (
    interpretar_cfop_decomposto,
    buscar_tipo_operacao_emissor,
    salvar_tipo_operacao_emissor,
    buscar_preferencia_empresa_fornecedor,
    salvar_preferencia_empresa_fornecedor,
    listar_cfops,
    adicionar_ou_atualizar_cfop
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
if "item_cfops_undo" not in st.session_state:
    # pilha de alterações em lote: cada item é uma lista de dicts {chave, nItem, old, new}
    st.session_state.item_cfops_undo = []
if "apply_busy" not in st.session_state:
    st.session_state.apply_busy = False

# Função para cadastrar empresa
def cadastrar_empresa(cnpj, razao_social, nome_fantasia):
    from sqlalchemy.exc import IntegrityError
    from src.db import engine, empresas, insert
    try:
        with engine.connect() as conn:
            stmt = insert(empresas).values(cnpj=cnpj, nome=nome_fantasia, razao_social=razao_social)
            conn.execute(stmt)
            conn.commit()
        return True
    except IntegrityError:
        st.error(f"CNPJ {cnpj} já está cadastrado. Selecione a empresa na lista.")
        return False
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

        # Barras de progresso para leitura
        total_nfe = len(files_copy_1)
        total_nfse = len(files_copy_2)
        prog_nfe = st.progress(0, text=f"NF-e 0/{total_nfe}")
        prog_nfse = st.progress(0, text=f"NFS-e 0/{total_nfse}")

        def _upd_nfe(i, total, name=None):
            if total:
                pct = int(i * 100 / total)
                txt = f"NF-e {i}/{total}"
                if name:
                    txt += f" — {name}"
                prog_nfe.progress(pct, text=txt)

        def _upd_nfse(i, total, name=None):
            if total:
                pct = int(i * 100 / total)
                txt = f"NFS-e {i}/{total}"
                if name:
                    txt += f" — {name}"
                prog_nfse.progress(pct, text=txt)

        # xml_reader.extrair_dados_xmls retorna df, arquivos_dict, itens_por_chave
        df_nfe, arquivos_nfe, itens_por_chave = extrair_dados_xmls(files_copy_1, progress_callback=_upd_nfe)
        df_nfse, arquivos_nfse = extrair_dados_nfses_xmls(files_copy_2, progress_callback=_upd_nfse)

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

    # Filtro por campo selecionado (com opção "Todos")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        opcoes_campos_notas = [
            "Todos",
            "fornecedor",
            "cnpj_emissor",
            "chave",
            "tipo_operacao",
            "data_nota",
            "complemento",
            "debito",
            "credito",
            "historico",
            "valor_total",
        ]
        filtro_campo_notas = st.selectbox(
            "Campo para busca",
            options=opcoes_campos_notas,
            index=opcoes_campos_notas.index(st.session_state.get("filtro_campo_notas", "Todos")) if st.session_state.get("filtro_campo_notas") in opcoes_campos_notas else 0,
            key="filtro_campo_notas",
        )
        filtro_texto = st.text_input("🔍 Buscar", value=st.session_state.get("filtro_texto", ""))
        st.session_state.filtro_texto = filtro_texto
    
    with col2:
        st.write("")
        st.write("")
        selecionar_todos = st.checkbox("Selecionar todos os filtrados", value=st.session_state.selecionar_todos)
        st.session_state.selecionar_todos = selecionar_todos

    # Aplicar filtro por campo ou todos
    if filtro_texto:
        base = st.session_state.df_geral.copy()
        texto = filtro_texto.strip().lower()
        try:
            if filtro_campo_notas == "Todos":
                mask = base.apply(
                    lambda r: texto in " ".join(["" if pd.isna(v) else str(v).lower() for v in r.values]),
                    axis=1,
                )
            else:
                col = filtro_campo_notas
                series = base[col].astype(str).str.lower() if col in base.columns else pd.Series([""] * len(base))
                mask = series.str.contains(texto, na=False)
            df_filtrado = base[mask].copy()
        except Exception:
            df_filtrado = base.copy()
        if df_filtrado.empty:
            st.warning(f"Nenhuma linha encontrada para '{filtro_texto}' em {filtro_campo_notas} — exibindo todas as notas.")
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
    
    # Adiciona coluna de seleção: preserva seleção anterior e respeita "Selecionar todos os filtrados"
    selecionadas_set = set(st.session_state.selected_rows or [])
    df_filtrado.insert(0, "Selecionar", df_filtrado["chave"].isin(selecionadas_set))
    if st.session_state.selecionar_todos:
        df_filtrado["Selecionar"] = True

    # Lista de CFOPs: carrega do catálogo no banco; fallback para padrão local
    DEFAULT_CFOPS_META = [
        {"codigo":"1102","categoria":"Consumo","nome":"Dentro do Estado"},
        {"codigo":"2102","categoria":"Consumo","nome":"Fora do Estado"},
        {"codigo":"1556","categoria":"Revenda","nome":"Dentro do Estado"},
        {"codigo":"2556","categoria":"Revenda","nome":"Fora do Estado"},
        {"codigo":"1126","categoria":"Ativo Imobilizado","nome":"Dentro do Estado"},
        {"codigo":"2126","categoria":"Ativo Imobilizado","nome":"Fora do Estado"},
        {"codigo":"1551","categoria":"Serviço","nome":"Dentro do Estado"},
        {"codigo":"2551","categoria":"Serviço","nome":"Fora do Estado"},
        {"codigo":"1405","categoria":"Tributos","nome":"Estaduais e Municipais"},
        {"codigo":"1403","categoria":"Revenda","nome":"Substituição tributária"},
        {"codigo":"1910","categoria":"Bonificação/Brinde","nome":"Doação ou brinde"},
        {"codigo":"2403","categoria":"Revenda","nome":"Para fora do Estado"},
        {"codigo":"2910","categoria":"Bonificação/Brinde","nome":"Outros Estados"},
        {"codigo":"5152","categoria":"Transferência","nome":"Dentro do Estado"},
        {"codigo":"6152","categoria":"Transferência","nome":"Fora do Estado"},
        {"codigo":"5910","categoria":"Bonificação/Brinde","nome":"Dentro do Estado"},
        {"codigo":"6910","categoria":"Bonificação/Brinde","nome":"Fora do Estado"},
        {"codigo":"5915","categoria":"Doação","nome":"Dentro do Estado"},
        {"codigo":"6915","categoria":"Doação","nome":"Fora do Estado"},
        {"codigo":"5920","categoria":"Demonstração","nome":"Dentro do Estado"},
        {"codigo":"6920","categoria":"Demonstração","nome":"Fora do Estado"},
        {"codigo":"5931","categoria":"Conserto","nome":"Remessa – Dentro do Estado"},
        {"codigo":"6931","categoria":"Conserto","nome":"Remessa – Fora do Estado"},
        {"codigo":"5932","categoria":"Conserto","nome":"Retorno – Dentro do Estado"},
        {"codigo":"6932","categoria":"Conserto","nome":"Retorno – Fora do Estado"},
        {"codigo":"5949","categoria":"Industrialização","nome":"Remessa – Dentro do Estado"},
        {"codigo":"6949","categoria":"Industrialização","nome":"Remessa – Fora do Estado"},
        {"codigo":"5951","categoria":"Industrialização","nome":"Retorno – Dentro do Estado"},
        {"codigo":"6951","categoria":"Industrialização","nome":"Retorno – Fora do Estado"},
    ]
    DEFAULT_CFOPS = [d["codigo"] for d in DEFAULT_CFOPS_META]

    def _seed_cfop_catalog_if_empty():
        try:
            rows = listar_cfops()
            if not rows:
                for d in DEFAULT_CFOPS_META:
                    try:
                        adicionar_ou_atualizar_cfop(d["codigo"], d.get("categoria"), d.get("nome"), d.get("descricao"))
                    except Exception:
                        pass
        except Exception:
            # Sem banco disponível; segue com fallback
            pass
    def _load_cfop_codes():
        try:
            # Faz seed inicial se estiver vazio
            _seed_cfop_catalog_if_empty()
            rows = listar_cfops()
            if rows:
                # Ordena por código numérico quando possível
                codes = sorted({r.get("codigo") for r in rows if r.get("codigo")}, key=lambda x: (len(x), x))
                return codes
        except Exception as e:
            pass
        return DEFAULT_CFOPS
    CFOP_CODES = _load_cfop_codes()

    # Gestão do catálogo de CFOPs (opcional): cadastrar novos códigos
    # Sidebar: gestão do catálogo de CFOPs (cadastrar/editar)
    with st.sidebar.expander("📚 Catálogo de CFOPs", expanded=False):
        try:
            rows = listar_cfops()
        except Exception:
            rows = []

        codigo_to_row = {r.get("codigo"): r for r in rows}
        opcoes = [""] + [f"{r.get('codigo')} - {r.get('nome') or ''}" for r in rows]
        selec = st.selectbox("Selecionar CFOP para editar", options=opcoes, key="cfop_edit_select")
        selec_codigo = selec.split(" - ")[0] if selec else ""
        dados = codigo_to_row.get(selec_codigo, {})

        colg1, colg2 = st.columns([1,1])
        with colg1:
            form_codigo = st.text_input("Código", value=dados.get("codigo", ""), max_chars=10, key="cfop_form_codigo")
            form_categoria = st.text_input("Categoria", value=dados.get("categoria", ""), max_chars=100, key="cfop_form_categoria")
        with colg2:
            form_nome = st.text_input("Nome", value=dados.get("nome", ""), max_chars=255, key="cfop_form_nome")
            form_desc = st.text_input("Descrição", value=dados.get("descricao", ""), max_chars=255, key="cfop_form_desc")

        colb1, colb2 = st.columns([1,1])
        with colb1:
            salvar_cfop_btn = st.button("Salvar CFOP", key="btn_salvar_cfop")
        with colb2:
            limpar_form_btn = st.button("Limpar", key="btn_limpar_cfop")

        if limpar_form_btn:
            for k in ["cfop_form_codigo", "cfop_form_categoria", "cfop_form_nome", "cfop_form_desc", "cfop_edit_select"]:
                st.session_state.pop(k, None)
            st.experimental_rerun() if hasattr(st, 'experimental_rerun') else rerun()

        if salvar_cfop_btn:
            try:
                code_s = (form_codigo or "").strip()
                cat_s = (form_categoria or "").strip() or None
                name_s = (form_nome or "").strip() or None
                desc_s = (form_desc or "").strip() or None
                if not code_s:
                    st.warning("Informe o código do CFOP.")
                else:
                    adicionar_ou_atualizar_cfop(code_s, cat_s, name_s, desc_s)
                    st.success(f"CFOP '{code_s}' salvo com sucesso.")
                    st.session_state["_last_cfop_added"] = code_s
                    rerun()
            except Exception as e:
                st.error(f"Erro ao salvar CFOP: {e}")

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
    st.caption(f"{len(st.session_state.selected_rows)} nota(s) selecionada(s) de {len(df_filtrado)} exibidas")

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
                if aplicar_todos_btn and cfop_para_todos and not st.session_state.apply_busy:
                    st.session_state.apply_busy = True
                    with st.spinner("Aplicando CFOP em todos os itens da nota, aguarde..."):
                        changes = []
                        count_local = 0
                        for item in itens:
                            nItem = str(item.get("nItem", ""))
                            old = st.session_state.item_cfops.get(chave, {}).get(nItem)
                            new = cfop_para_todos
                            if chave not in st.session_state.item_cfops:
                                st.session_state.item_cfops[chave] = {}
                            st.session_state.item_cfops[chave][nItem] = new
                            changes.append({"chave": chave, "nItem": nItem, "old": old, "new": new})
                            count_local += 1
                        if changes:
                            st.session_state.item_cfops_undo.append(changes)
                    st.session_state.apply_busy = False
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

            col_f0, col_f1, col_f2, col_f3 = st.columns([1, 2, 1, 1])
            with col_f0:
                usar_filtro_notas = st.checkbox("Usar filtro das notas", value=False, key="usar_filtro_notas")
            with col_f1:
                opcoes_campos_itens = [
                    "Todos",
                    "xProd",
                    "fornecedor",
                    "chave",
                    "cfop_atual",
                    "nItem",
                    "vProd",
                ]
                filtro_campo_itens = st.selectbox(
                    "Campo para busca (itens)",
                    options=opcoes_campos_itens,
                    index=opcoes_campos_itens.index(st.session_state.get("filtro_campo_itens", "Todos")) if st.session_state.get("filtro_campo_itens") in opcoes_campos_itens else 0,
                    key="filtro_campo_itens",
                )
                filtro_itens_input = st.text_input(
                    "Buscar nos itens",
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
            filtro_itens_val = (st.session_state.get("filtro_texto", "") if usar_filtro_notas else filtro_itens_input)
            filtro_campo_aplicado = (st.session_state.get("filtro_campo_notas", "Todos") if usar_filtro_notas else filtro_campo_itens)
            if filtro_itens_val:
                texto = filtro_itens_val.strip().lower()
                try:
                    if filtro_campo_aplicado == "Todos":
                        mask = df_itens.apply(
                            lambda r: texto in " ".join([str(v).lower() for v in r.values if v is not None]),
                            axis=1,
                        )
                    else:
                        col = filtro_campo_aplicado
                        series = df_itens[col].astype(str).str.lower() if col in df_itens.columns else pd.Series([""] * len(df_itens))
                        mask = series.str.contains(texto, na=False)
                    df_filtrado = df_itens[mask].copy()
                except Exception:
                    df_filtrado = df_itens.copy()
                if df_filtrado.empty:
                    st.info("Nenhum item encontrado com o filtro informado; exibindo todos.")
                    df_filtrado = df_itens.copy()

            # Marcar todos os filtrados se solicitado
            if itens_select_all and not df_filtrado.empty:
                df_filtrado["Selecionar"] = True

            st.caption(f"{len(df_filtrado)} item(ns) no filtro atual")

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
                aplicar_cfop_itens_btn = st.button("Aplicar CFOP aos itens selecionados", disabled=st.session_state.apply_busy)

            if aplicar_cfop_itens_btn and not st.session_state.apply_busy:
                # Seleciona os itens marcados; se 'selecionar todos' estiver ativo e nenhum marcado manualmente,
                # aplica em todos os itens do conjunto filtrado atual
                selected_items = edited_items_df[edited_items_df["Selecionar"] == True]
                if itens_select_all and selected_items.empty:
                    selected_items = edited_items_df
                if novo_cfop_itens:
                    st.session_state.apply_busy = True
                    with st.spinner("Aplicando CFOP nos itens selecionados, aguarde..."):
                        changes = []
                        count = 0
                        for _, row_it in selected_items.iterrows():
                            chave = row_it["chave"]
                            nItem = str(row_it["nItem"])
                            old = st.session_state.item_cfops.get(chave, {}).get(nItem)
                            new = novo_cfop_itens
                            if chave not in st.session_state.item_cfops:
                                st.session_state.item_cfops[chave] = {}
                            st.session_state.item_cfops[chave][nItem] = new
                            changes.append({"chave": chave, "nItem": nItem, "old": old, "new": new})
                            count += 1
                        if changes:
                            st.session_state.item_cfops_undo.append(changes)
                    st.session_state.apply_busy = False
                    st.success(f"CFOP '{novo_cfop_itens}' aplicado em {count} item(ns)")
                else:
                    st.warning("Selecione um CFOP para aplicar em lote.")

            st.divider()
            # Desfazer última aplicação em lote
            col_u1, col_u2 = st.columns([2, 1])
            with col_u1:
                undo_label = "↩️ Desfazer última aplicação" if st.session_state.item_cfops_undo else "↩️ Nada para desfazer"
            with col_u2:
                undo_btn = st.button(undo_label, disabled=not bool(st.session_state.item_cfops_undo))
            if undo_btn:
                changes = st.session_state.item_cfops_undo.pop()
                restored = 0
                for ch in changes:
                    chave = ch["chave"]
                    nItem = ch["nItem"]
                    old = ch.get("old")
                    if chave not in st.session_state.item_cfops:
                        st.session_state.item_cfops[chave] = {}
                    # Se old é None, removemos a entrada para voltar ao estado "sem seleção"
                    if old is None:
                        if nItem in st.session_state.item_cfops[chave]:
                            del st.session_state.item_cfops[chave][nItem]
                    else:
                        st.session_state.item_cfops[chave][nItem] = old
                    restored += 1
                st.success(f"Desfeita a última aplicação em {restored} item(ns)")
            # Aplicar CFOP a todos os itens de todas as notas selecionadas
            col_all1, col_all2 = st.columns([2, 1])
            with col_all1:
                cfop_todos_itens_de_todas_notas = st.selectbox(
                    "CFOP para TODOS os itens das notas selecionadas:",
                    [""] + CFOP_CODES,
                    index=0,
                    key="cfop_todos_itens_de_todas_notas",
                )
            with col_all2:
                aplicar_todos_itens_btn = st.button("Aplicar a todos os itens de todas as notas selecionadas", disabled=st.session_state.apply_busy)
            if aplicar_todos_itens_btn and not st.session_state.apply_busy:
                if cfop_todos_itens_de_todas_notas:
                    st.session_state.apply_busy = True
                    with st.spinner("Aplicando CFOP em todos os itens das notas selecionadas, aguarde..."):
                        changes = []
                        total = 0
                        for _, nota in notas_selecionadas.iterrows():
                            chave = nota["chave"]
                            itens = st.session_state.itens_por_chave.get(chave, [])
                            if chave not in st.session_state.item_cfops:
                                st.session_state.item_cfops[chave] = {}
                            for item in itens:
                                nItem = str(item.get("nItem", ""))
                                old = st.session_state.item_cfops.get(chave, {}).get(nItem)
                                new = cfop_todos_itens_de_todas_notas
                                st.session_state.item_cfops[chave][nItem] = new
                                changes.append({"chave": chave, "nItem": nItem, "old": old, "new": new})
                                total += 1
                        if changes:
                            st.session_state.item_cfops_undo.append(changes)
                    st.session_state.apply_busy = False
                    st.success(f"CFOP '{cfop_todos_itens_de_todas_notas}' aplicado em {total} item(ns) nas notas selecionadas")
                else:
                    st.warning("Selecione um CFOP para aplicar em todos os itens.")
    # Preencher Débito/Crédito/Histórico em massa (sem alterar CFOP)
    st.divider()
    st.subheader("🧮 Preencher Débito/Crédito/Histórico em massa")
    colm1, colm2 = st.columns([2, 1])
    with colm1:
        aplicar_em_filtradas = st.checkbox(
            "Aplicar a todas as notas filtradas (ignora seleção)", value=False
        )
        st.caption(
            f"Selecionadas: {len(st.session_state.selected_rows)} | Filtradas na tabela: {len(df_filtrado)}"
        )
    with colm2:
        pass

    colc1, colc2, colc3, colc4 = st.columns([1, 1, 1, 1])
    with colc1:
        novo_debito = st.text_input("Débito (13 dígitos)", max_chars=13, key="debito_mass")
    with colc2:
        novo_credito = st.text_input("Crédito (13 dígitos)", max_chars=13, key="credito_mass")
    with colc3:
        novo_historico = st.text_input("Histórico (9 dígitos)", max_chars=9, key="historico_mass")
    with colc4:
        aplicar_vals_btn = st.button("Aplicar nas notas alvo", use_container_width=True)

    if aplicar_vals_btn:
        # Determina as chaves alvo: todas filtradas ou apenas selecionadas
        if aplicar_em_filtradas:
            chaves_alvo = set(df_filtrado["chave"].tolist())
        else:
            chaves_alvo = set(st.session_state.selected_rows or [])

        if not chaves_alvo:
            st.warning("Nenhuma nota alvo. Selecione notas ou marque 'Aplicar a todas as notas filtradas'.")
        else:
            count = 0
            for chave in chaves_alvo:
                idxs = st.session_state.df_geral.index[st.session_state.df_geral["chave"] == chave].tolist()
                for idx in idxs:
                    if novo_debito:
                        st.session_state.df_geral.at[idx, "debito"] = novo_debito
                    if novo_credito:
                        st.session_state.df_geral.at[idx, "credito"] = novo_credito
                    if novo_historico:
                        st.session_state.df_geral.at[idx, "historico"] = novo_historico
                    count += 1
            st.success(f"Valores aplicados em {count} linha(s) de nota (sem alterar CFOP)")

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
