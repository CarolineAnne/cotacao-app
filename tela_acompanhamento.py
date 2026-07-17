import io
from datetime import datetime

import pandas as pd
import streamlit as st


def tela_acompanhamento(supabase):
    st.title("📌 Acompanhamento do Sistema")

    try:
        resp = (
            supabase
            .table("acompanhamento")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        df_acomp = pd.DataFrame(resp.data)

    except Exception as e:
        st.error(f"Erro ao carregar acompanhamento: {e}")
        st.stop()

    if df_acomp.empty:
        st.info("Nenhuma ação registrada até o momento.")
        st.stop()

    st.subheader("🔎 Filtros")

    df_acomp["data"] = pd.to_datetime(df_acomp["data"], errors="coerce")

    col1, col2, col3 = st.columns(3)

    with col1:
        data_filtro = st.date_input("Data", value=datetime.now().date())

    with col2:
        usuarios = ["Todos"] + sorted(
            df_acomp["usuario"].dropna().unique().tolist()
        )
        usuario_filtro = st.selectbox("Usuário", usuarios)

    with col3:
        telas = ["Todas"] + sorted(
            df_acomp["tela"].dropna().unique().tolist()
        )
        tela_filtro = st.selectbox("Tela", telas)

    df_filtrado = df_acomp[df_acomp["data"].dt.date == data_filtro]

    if usuario_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["usuario"] == usuario_filtro]

    if tela_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["tela"] == tela_filtro]

    st.subheader("📋 Registro de Atividades")

    df_tabela = df_filtrado.copy()

    if "data" in df_tabela.columns:
        df_tabela["data"] = df_tabela["data"].dt.strftime("%d/%m/%Y")

    colunas_exibir = [
        "data",
        "hora",
        "usuario",
        "nivel",
        "tela",
        "acao",
        "detalhes",
        "arquivo_url"
    ]

    colunas_existentes = [
        c
        for c in colunas_exibir
        if c in df_tabela.columns
    ]

    st.dataframe(
        df_tabela[colunas_existentes],
        width="stretch"
    )

    st.divider()
    st.subheader("📎 Arquivos PDF disponíveis")

    df_pdfs = df_filtrado[
        df_filtrado["arquivo_url"].notna() &
        (df_filtrado["arquivo_url"].astype(str).str.strip() != "")
    ]

    if df_pdfs.empty:
        st.info("Nenhum PDF registrado nesse período.")
    else:
        for _, row in df_pdfs.iterrows():
            st.markdown(
                f"""
                **{row.get('data').strftime('%d/%m/%Y') if pd.notnull(row.get('data')) else ''}**
                — {row.get('hora', '')}  
                **Usuário:** {row.get('usuario', '')}  
                **Ação:** {row.get('acao', '')}  
                [📥 Baixar PDF]({row.get('arquivo_url', '')})
                """
            )

    st.divider()

    try:
        buffer = io.BytesIO()
        df_tabela[colunas_existentes].to_excel(
            buffer,
            index=False,
            engine="openpyxl"
        )
        buffer.seek(0)

        st.download_button(
            "📥 Exportar Acompanhamento em Excel",
            buffer,
            file_name=f"acompanhamento_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
        )

    except Exception as e:
        st.error(f"Erro ao gerar Excel: {e}")
