import io
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


def tela_visualizar_dados(supabase):
    st.title("📋 Cotações")

    col1, col2 = st.columns(2)
    hoje = datetime.now().date()

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

    if df.empty:
        st.warning(f"Não há cotações cadastradas para {data_ref.strftime('%d/%m/%Y')}.")
        df_tabela = pd.DataFrame()

    else:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"])

        df["produto"] = df["produto"].astype(str).str.strip().str.upper()

        df["classe"] = df["classe"].astype(str).str.strip()
        df["classe"] = df["classe"].replace("", "SEM CLASSE")
        df["classe"] = df["classe"].fillna("").apply(corrigir_classe)

        if "kg" in df.columns:
            df["kg"] = pd.to_numeric(
                df["kg"],
                errors="coerce"
            ).fillna(0).astype(int)

        if classe != "Todas":
            df = df[df["classe"] == classe]

        df["classe"] = pd.Categorical(
            df["classe"],
            categories=ORDEM_CLASSES,
            ordered=True
        )

        df = df.sort_values(["classe", "produto"])

        df_tabela = df.drop(
            columns=[c for c in ["id", "data"] if c in df.columns]
        ).copy()

        cols_preco = ["preco_min", "preco_max", "preco_medio", "valor_kg"]

        for col in cols_preco:
            if col in df_tabela.columns:
                df_tabela[col] = df_tabela[col].apply(
                    lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
                )

        st.dataframe(df_tabela, use_container_width=True)

    gerar_pdf_click = st.button("📄 Gerar PDF")

    if gerar_pdf_click:
        try:
            if df.empty:
                st.warning("Não há dados para gerar PDF nesta data.")
            else:
                nome_pdf = f"cotacoes_{data_ref.strftime('%d-%m-%Y')}.pdf"

                gerar_pdf(df, nome_pdf)

                with open(nome_pdf, "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF",
                        f,
                        file_name=nome_pdf
                    )

        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

    if st.session_state.get("nivel") == "admin":
        st.divider()
        st.subheader("📥 Exportações do Administrador")

        try:
            if not df_tabela.empty:
                buffer = io.BytesIO()
                df_tabela.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)

                st.download_button(
                    "📥 Baixar Excel da Data Filtrada",
                    buffer,
                    file_name=f"cotacoes_filtradas_{data_ref.strftime('%d-%m-%Y')}.xlsx"
                )

            df_todas_cotacoes = carregar_todas_cotacoes(supabase)

            if df_todas_cotacoes.empty:
                st.info("Não há cotações para exportar.")
            else:
                df_exportar_todas = df_todas_cotacoes.copy()

                df_exportar_todas["data"] = pd.to_datetime(
                    df_exportar_todas["data"],
                    errors="coerce"
                ).dt.strftime("%d/%m/%Y")

                df_exportar_todas["produto"] = (
                    df_exportar_todas["produto"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )
                df_exportar_todas["classe"] = df_exportar_todas["classe"].apply(corrigir_classe)

                if "kg" in df_exportar_todas.columns:
                    df_exportar_todas["kg"] = pd.to_numeric(
                        df_exportar_todas["kg"],
                        errors="coerce"
                    ).fillna(0).astype(int)

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
