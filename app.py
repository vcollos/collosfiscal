import streamlit as st
from streamlit import rerun
import pandas as pd
import zipfile
import io

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

st.set_page_config(page_title="CollosFiscal Pro - NF-e e NFSe Inteligente", layout="wide")
st.title("🧾 CollosFiscal Pro - NF-e e NFSe Inteligente")

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

# Função para cadastrar empresa
def cadastrar_empresa(cnpj, razao_social, nome_fantasia):
    from src.db import engine, Table, MetaData, insert
    metadata = MetaData()
    metadata.reflect(bind=engine)
    empresas_table = Table('empresas', metadata, autoload_with=engine)
    with engine.connect() as conn:
        stmt = insert(empresas_table).values(cnpj=cnpj, nome=nome_fantasia, razao_social=razao_social)
        conn.execute(stmt)
        conn.commit()

# Seleção da empresa no início da sessão com opção de cadastro
if st.session_state.empresa_selecionada is None:
    from src.db import engine, Table, MetaData
    metadata = MetaData()
    metadata.reflect(bind=engine)
    empresas_table = Table('empresas', metadata, autoload_with=engine)
    with engine.connect() as conn:
        result = conn.execute(empresas_table.select())
        empresas = result.fetchall()
    empresa_options = {row[2]: row[0] for row in empresas}  # Ajuste para acessar por índice, nome na posição 2, id na posição 0

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
                    cadastrar_empresa(cnpj, razao_social, nome_fantasia)
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

        df_nfe, arquivos_nfe = extrair_dados_xmls(files_copy_1)
        df_nfse, arquivos_nfse = extrair_dados_nfses_xmls(files_copy_2)

        st.session_state.df_geral = pd.concat([df_nfe, df_nfse], ignore_index=True)  # Atualizando df_geral no session state
        arquivos_dict = {**arquivos_nfe, **arquivos_nfse}
        st.session_state.arquivos_dict = arquivos_dict  # Salva no session state

        # Garante que as colunas existam
        if "tipo_operacao" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["tipo_operacao"] = ""
        if "data_nota" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["data_nota"] = ""
        if "complemento" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["complemento"] = ""

        # Adiciona colunas Debito, Credito e Historico se não existirem
        if "debito" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["debito"] = ""
        if "credito" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["credito"] = ""
        if "historico" not in st.session_state.df_geral.columns:
            st.session_state.df_geral["historico"] = ""

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
            for col in ["debito", "credito", "historico"]:
                if col not in df_filtrado.columns:
                    df_filtrado[col] = ""
    else:
        df_filtrado = st.session_state.df_geral.copy()
        # Garante que as colunas Debito, Credito e Historico estejam presentes no df_filtrado
        for col in ["debito", "credito", "historico"]:
            if col not in df_filtrado.columns:
                df_filtrado[col] = ""
    
    # Adiciona coluna de seleção
    df_filtrado.insert(0, "Selecionar", st.session_state.selecionar_todos)
    
    # Exibe o dataframe com opção de editar a coluna tipo_operação e novas colunas
    edited_df = st.data_editor(
        df_filtrado,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar",
                help="Selecione as linhas para edição em massa",
                default=False
            ),
            "tipo_operacao": st.column_config.SelectboxColumn(
                "Tipo Operação",
                help="Tipo de operação (CFOP code)",
                width="medium",
                options=[
                    "",
                    "1102",
                    "2102",
                    "1556",
                    "2556",
                    "1126",
                    "2126",
                    "1551",
                    "2551",
                ],
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
                width="large",
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
    
    # Atualiza o dataframe original com as edições individuais feitas pelo usuário
    for idx, row in edited_df.iterrows():
        chave = row["chave"]
        tipo_operacao = row["tipo_operacao"]
        data_nota = row.get("data_nota", "")
        complemento = row.get("complemento", "")
        debito = row.get("debito", "")
        credito = row.get("credito", "")
        historico = row.get("historico", "")
        # Atualiza todas as colunas editáveis, mesmo que tipo_operacao esteja vazio
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "tipo_operacao"] = tipo_operacao
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "data_nota"] = data_nota
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "complemento"] = complemento
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "debito"] = debito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "credito"] = credito
        st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chave, "historico"] = historico
    
    st.divider()

    # Alterar tipo de operação em massa
    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
    
    with col1:
        novo_tipo = st.selectbox("🚀 Tipo de operação para aplicar nos selecionados:", [
            "Revenda dentro do estado",
            "Revenda fora do estado",
            "Consumo dentro do estado",
            "Consumo fora do estado",
            "Serviço dentro do estado",
            "Serviço fora do estado",
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
                from src.utils import CFOP_MAP
                tipo_operacao_map = {
                    "Revenda dentro do estado": "Revenda - Dentro do Estado",
                    "Revenda fora do estado": "Revenda - Fora do Estado",
                    "Consumo dentro do estado": "Consumo - Dentro do Estado",
                    "Consumo fora do estado": "Consumo - Fora do Estado",
                    "Serviço dentro do estado": "Serviço - Dentro do Estado",
                    "Serviço fora do estado": "Serviço - Fora do Estado",
                }
                # Converte o texto selecionado para o código CFOP
                cfop_code = CFOP_MAP.get(tipo_operacao_map.get(novo_tipo, ""), "")
                # Guarda as chaves das linhas selecionadas
                chaves_selecionadas = selected_rows["chave"].tolist()
                
                # Atualiza o dataframe no session state com o código CFOP
                for chave in chaves_selecionadas:
                    idxs = st.session_state.df_geral.index[st.session_state.df_geral["chave"] == chave].tolist()
                    for idx in idxs:
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
        for idx, row in st.session_state.df_geral.iterrows():
            cnpj = row["cnpj_emissor"]
            cfop_code = row["tipo_operacao"]
            data_nota = row.get("data_nota", "")
            complemento = row.get("complemento", "")
            debito = row.get("debito", "")
            credito = row.get("credito", "")
            historico = row.get("historico", "")
            if cnpj and cfop_code:
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
    if st.button("📦 Gerar ZIP com XMLs alterados"):
        from src.xml_editor import alterar_cfops_e_gerar_zip
        chaves_alteradas = st.session_state.df_geral[st.session_state.df_geral["tipo_operacao"] != ""]["chave"].tolist()
        if not chaves_alteradas:
            st.warning("Nenhuma nota com tipo de operação alterado para gerar XML.")
        else:
            zip_buffer = alterar_cfops_e_gerar_zip(st.session_state.arquivos_dict, chaves_alteradas, novo_cfop=st.session_state.df_geral.loc[st.session_state.df_geral["chave"] == chaves_alteradas[0], "tipo_operacao"].values[0])
            st.download_button(
                label="⬇️ Baixar ZIP com XMLs alterados",
                data=zip_buffer,
                file_name="notas_alteradas.zip",
                mime="application/zip"
            )

    # Gerar e exportar CSV com dados selecionados
    if st.button("📄 Gerar CSV com dados selecionados"):
        import csv
        import tempfile

        csv_columns = ["debito", "credito", "historico", "data_nota", "valor_total", "complemento"]
        df_csv = st.session_state.df_geral[csv_columns].copy()

        # Criar arquivo CSV temporário
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, newline='', suffix=".csv") as tmpfile:
            df_csv.to_csv(tmpfile.name, index=False)
            tmpfile.seek(0)
            csv_data = tmpfile.read()

        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv_data,
            file_name="dados_notas.csv",
            mime="text/csv"
        )
