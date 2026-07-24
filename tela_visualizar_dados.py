import io
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from dados_utils import carregar_todas_cotacoes
from pdf_utils import gerar_pdf
from utils import corrigir_classe


ORDEM_CLASSES = [
    "Hortaliças",
    "Frutas",
    "Especiarias",
    "Cereais",
    "SEM CLASSE"
]


def formatar_data_arquivo(data):
    return data.strftime("%d-%m-%Y")


def gerar_pdf_para_download(df):
    caminho_pdf = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            caminho_pdf = temp_pdf.name

        gerar_pdf(df, caminho_pdf)

        with open(caminho_pdf, "rb") as arquivo_pdf:
            return arquivo_pdf.read()

    finally:
        if caminho_pdf and os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)


def preparar_dataframe_cotacoes(df):
    df = df.copy()

    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    df["produto"] = (
        df["produto"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["classe"] = df["classe"].astype(str).str.strip()
    df["classe"] = df["classe"].replace("", "SEM CLASSE")
    df["classe"] = df["classe"].fillna("").apply(corrigir_classe)

    if "kg" in df.columns:
        df["kg"] = pd.to_numeric(
            df["kg"],
            errors="coerce"
        ).fillna(0).astype(int)

    cols_preco = ["preco_min", "preco_max", "preco_medio", "valor_kg"]

    for col in cols_preco:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

    return df


def aplicar_ordenacao(df):
    df = df.copy()

    if df.empty:
        return df

    df["classe"] = pd.Categorical(
        df["classe"],
        categories=ORDEM_CLASSES,
        ordered=True
    )

    colunas_ordem = []

    if "data" in df.columns:
        colunas_ordem.append("data")

    colunas_ordem.extend(["classe", "produto"])

    df = df.sort_values(colunas_ordem)

    return df


def formatar_tabela_exibicao(df, mostrar_data=False):
    df_tabela = df.copy()

    colunas_remover = ["id"]

    if not mostrar_data:
        colunas_remover.append("data")

    df_tabela = df_tabela.drop(
        columns=[c for c in colunas_remover if c in df_tabela.columns]
    ).copy()

    if mostrar_data and "data" in df_tabela.columns:
        df_tabela["data"] = pd.to_datetime(
            df_tabela["data"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    cols_preco = ["preco_min", "preco_max", "preco_medio", "valor_kg"]

    for col in cols_preco:
        if col in df_tabela.columns:
            df_tabela[col] = df_tabela[col].apply(
                lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
            )

    return df_tabela


def tela_visualizar_dados(supabase):
    st.title("📋 Cotações")

    nivel = st.session_state.get("nivel", "")

    hoje = datetime.now().date()

    # =====================================================
    # FILTROS
    # Admin: data inicial, data final, classe e produto.
    # Outros níveis: mantém o padrão antigo, com apenas data e classe.
    # =====================================================
    if nivel == "admin":
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            data_inicial = st.date_input(
                "Data inicial",
                value=hoje,
                key="data_inicial_visualizar_dados_admin"
            )

        with col2:
            data_final = st.date_input(
                "Data final",
                value=hoje,
                key="data_final_visualizar_dados_admin"
            )

        if data_inicial > data_final:
            st.warning("A data inicial não pode ser maior que a data final.")
            return

        data_inicial_sql = data_inicial.strftime("%Y-%m-%d")
        data_final_sql = data_final.strftime("%Y-%m-%d")

        try:
            df = carregar_todas_cotacoes(supabase)

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.stop()

        df = preparar_dataframe_cotacoes(df)

        if not df.empty:
            data_inicial_ts = pd.to_datetime(data_inicial)
            data_final_ts = pd.to_datetime(data_final) + pd.Timedelta(days=1)

            df = df[
                (df["data"] >= data_inicial_ts) &
                (df["data"] < data_final_ts)
            ].copy()

        with col3:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"],
                key="classe_visualizar_dados_admin"
            )

        # Primeiro aplica classe para montar a lista de produtos conforme o filtro.
        df_para_produtos = df.copy()

        if not df_para_produtos.empty and classe != "Todas":
            df_para_produtos = df_para_produtos[df_para_produtos["classe"] == classe]

        if df_para_produtos.empty:
            produtos_lista = ["Todos"]
        else:
            produtos_lista = ["Todos"] + sorted(
                df_para_produtos["produto"]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .unique()
                .tolist()
            )

        with col4:
            produto = st.selectbox(
                "Produto",
                produtos_lista,
                key="produto_visualizar_dados_admin"
            )

        if not df.empty and classe != "Todas":
            df = df[df["classe"] == classe]

        if not df.empty and produto != "Todos":
            df = df[df["produto"] == produto]

        mostrar_data = True

        periodo_texto = (
            f"{data_inicial.strftime('%d/%m/%Y')} a "
            f"{data_final.strftime('%d/%m/%Y')}"
        )

    else:
        col1, col2 = st.columns(2)

        with col1:
            data_ref = st.date_input(
                "Data",
                value=hoje,
                key="data_visualizar_dados"
            )

        with col2:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais"],
                key="classe_visualizar_dados"
            )

        data_sql = data_ref.strftime("%Y-%m-%d")

        try:
            resp = (
                supabase
                .table("cotacoes")
                .select("id, data, classe, produto, unidade, kg, preco_min, preco_max, preco_medio, valor_kg")
                .eq("data", data_sql)
                .order("produto")
                .execute()
            )

            df = pd.DataFrame(resp.data or [])

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.stop()

        df = preparar_dataframe_cotacoes(df)

        if not df.empty and classe != "Todas":
            df = df[df["classe"] == classe]

        mostrar_data = False
        periodo_texto = data_ref.strftime("%d/%m/%Y")

    # =====================================================
    # EXIBIÇÃO
    # =====================================================
    if df.empty:
        if nivel == "admin":
            st.warning(f"Não há cotações cadastradas para o período {periodo_texto}.")
        else:
            st.warning(f"Não há cotações cadastradas para {periodo_texto}.")

        df_tabela = pd.DataFrame()

    else:
        df = aplicar_ordenacao(df)
        df_tabela = formatar_tabela_exibicao(df, mostrar_data=mostrar_data)

        st.caption(f"Registros encontrados: {len(df)}")

        st.dataframe(df_tabela, width="stretch")

    # =====================================================
    # PDF
    # =====================================================
    gerar_pdf_click = st.button("📄 Gerar PDF")

    if gerar_pdf_click:
        try:
            if df.empty:
                st.warning("Não há dados para gerar PDF com os filtros selecionados.")
            else:
                if nivel == "admin":
                    nome_pdf = (
                        f"cotacoes_"
                        f"{formatar_data_arquivo(data_inicial)}_a_"
                        f"{formatar_data_arquivo(data_final)}.pdf"
                    )
                else:
                    nome_pdf = f"cotacoes_{formatar_data_arquivo(data_ref)}.pdf"

                pdf_bytes = gerar_pdf_para_download(df)

                st.download_button(
                    "📥 Baixar PDF",
                    pdf_bytes,
                    file_name=nome_pdf,
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

    # =====================================================
    # EXPORTAÇÕES DO ADMINISTRADOR
    # =====================================================
    if nivel == "admin":
        st.divider()
        st.subheader("📥 Exportações do Administrador")

        try:
            if not df_tabela.empty:
                buffer = io.BytesIO()
                df_tabela.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)

                st.download_button(
                    "📥 Baixar Excel do Período Filtrado",
                    buffer,
                    file_name=(
                        f"cotacoes_filtradas_"
                        f"{formatar_data_arquivo(data_inicial)}_a_"
                        f"{formatar_data_arquivo(data_final)}.xlsx"
                    )
                )

            df_todas_cotacoes = carregar_todas_cotacoes(supabase)

            if df_todas_cotacoes.empty:
                st.info("Não há cotações para exportar.")
            else:
                df_exportar_todas = df_todas_cotacoes.copy()

                df_exportar_todas = preparar_dataframe_cotacoes(df_exportar_todas)

                if not df_exportar_todas.empty:
                    df_exportar_todas["data"] = pd.to_datetime(
                        df_exportar_todas["data"],
                        errors="coerce"
                    ).dt.strftime("%d/%m/%Y")

                    df_exportar_todas["classe"] = pd.Categorical(
                        df_exportar_todas["classe"],
                        categories=ORDEM_CLASSES,
                        ordered=True
                    )

                    df_exportar_todas = df_exportar_todas.sort_values(
                        ["data", "classe", "produto"]
                    )

                buffer_todas = io.BytesIO()
                df_exportar_todas.to_excel(
                    buffer_todas,
                    index=False,
                    engine="openpyxl"
                )
                buffer_todas.seek(0)

                st.download_button(
                    "📥 Exportar Todas as Cotações",
                    buffer_todas,
                    file_name=f"todas_cotacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
                )

        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")
