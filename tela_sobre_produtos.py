from datetime import datetime

import pandas as pd
import streamlit as st

from dados_utils import carregar_produtos, registrar_acao
from pdf_utils import gerar_pdf_sobre_produtos
from utils import corrigir_classe


ORDEM_CLASSES_MAP = {
    "Hortaliças": 1,
    "Frutas": 2,
    "Especiarias": 3,
    "Cereais": 4,
    "SEM CLASSE": 99
}

ORDEM_CLASSES = [
    "Hortaliças",
    "Frutas",
    "Especiarias",
    "Cereais",
    "SEM CLASSE"
]


def carregar_produtos_ordenados(supabase):
    produtos = carregar_produtos(supabase)

    if produtos.empty:
        return produtos

    produtos["nome"] = produtos["nome"].astype(str).str.strip().str.upper()
    produtos["classe"] = produtos["classe"].apply(corrigir_classe)
    produtos["ordem_classe"] = produtos["classe"].map(ORDEM_CLASSES_MAP).fillna(99)
    produtos = produtos.sort_values(["ordem_classe", "nome"])
    produtos = produtos.drop(columns=["ordem_classe"])

    return produtos


def tela_sobre_produtos(supabase, nivel):
    st.title("📝 Sobre os Produtos")

    try:
        produtos = carregar_produtos_ordenados(supabase)

        if produtos.empty:
            st.warning("Nenhum produto cadastrado.")
            st.stop()

    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        st.stop()

    if nivel in ["admin", "cotacao"]:
        st.subheader("➕ Cadastrar / Atualizar Informação do Produto")

        produto_sel = st.selectbox(
            "Produto",
            produtos["nome"].tolist(),
            key="sobre_produto_sel"
        )

        dados_produto = produtos[produtos["nome"] == produto_sel].iloc[0]
        classe_produto = dados_produto["classe"]

        try:
            resp_info = (
                supabase
                .table("informacoes_produtos")
                .select("*")
                .eq("produto", produto_sel)
                .execute()
            )

            info_existente = pd.DataFrame(resp_info.data)

            if not info_existente.empty:
                texto_atual = str(info_existente.iloc[0].get("informacoes", ""))
            else:
                texto_atual = ""

        except Exception:
            texto_atual = ""

        informacoes = st.text_area(
            "Informações sobre o produto",
            value=texto_atual,
            height=180,
            key=f"info_{produto_sel}"
        )

        if st.button("💾 Salvar Informações"):
            if informacoes.strip() == "":
                st.warning("Digite alguma informação antes de salvar.")

            else:
                try:
                    agora = datetime.now()

                    resp_verifica = (
                        supabase
                        .table("informacoes_produtos")
                        .select("id")
                        .eq("produto", produto_sel)
                        .execute()
                    )

                    dados_existentes = pd.DataFrame(resp_verifica.data)

                    if dados_existentes.empty:
                        supabase.table("informacoes_produtos").insert({
                            "produto": produto_sel,
                            "classe": classe_produto,
                            "informacoes": informacoes.strip(),
                            "atualizado_por": st.session_state.get("nome", ""),
                            "nivel_usuario": nivel,
                            "data_atualizacao": agora.strftime("%Y-%m-%d"),
                            "hora_atualizacao": agora.strftime("%H:%M:%S")
                        }).execute()

                        registrar_acao(
                            supabase,
                            "Cadastro de informação de produto",
                            "Sobre os Produtos",
                            f"Informação cadastrada para o produto: {produto_sel}"
                        )

                        st.success("Informações cadastradas com sucesso!")

                    else:
                        id_info = int(dados_existentes.iloc[0]["id"])

                        supabase.table("informacoes_produtos").update({
                            "classe": classe_produto,
                            "informacoes": informacoes.strip(),
                            "atualizado_por": st.session_state.get("nome", ""),
                            "nivel_usuario": nivel,
                            "data_atualizacao": agora.strftime("%Y-%m-%d"),
                            "hora_atualizacao": agora.strftime("%H:%M:%S")
                        }).eq("id", id_info).execute()

                        registrar_acao(
                            supabase,
                            "Atualização de informação de produto",
                            "Sobre os Produtos",
                            f"Informação atualizada para o produto: {produto_sel}"
                        )

                        st.success("Informações atualizadas com sucesso!")

                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao salvar informações: {e}")

        st.divider()

    st.subheader("📋 Informações Cadastradas")

    try:
        resp_infos = (
            supabase
            .table("informacoes_produtos")
            .select("*")
            .execute()
        )

        df_infos = pd.DataFrame(resp_infos.data)

    except Exception as e:
        st.error(f"Erro ao carregar informações dos produtos: {e}")
        st.stop()

    if df_infos.empty:
        st.info("Nenhuma informação cadastrada até o momento.")
        st.stop()

    df_infos["produto"] = df_infos["produto"].astype(str).str.strip().str.upper()
    df_infos["classe"] = df_infos["classe"].apply(corrigir_classe)

    if "data_atualizacao" in df_infos.columns:
        df_infos["data_atualizacao"] = pd.to_datetime(
            df_infos["data_atualizacao"],
            errors="coerce"
        )

    col1, col2 = st.columns(2)

    with col1:
        filtro_classe = st.selectbox(
            "Filtrar por classe",
            ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"],
            key="filtro_classe_sobre"
        )

    with col2:
        lista_produtos = ["Todos"] + sorted(
            df_infos["produto"].dropna().unique().tolist()
        )

        filtro_produto = st.selectbox(
            "Filtrar por produto",
            lista_produtos,
            key="filtro_produto_sobre"
        )

    df_filtrado = df_infos.copy()

    if filtro_classe != "Todas":
        df_filtrado = df_filtrado[df_filtrado["classe"] == filtro_classe]

    if filtro_produto != "Todos":
        df_filtrado = df_filtrado[df_filtrado["produto"] == filtro_produto]

    df_filtrado["classe"] = pd.Categorical(
        df_filtrado["classe"],
        categories=ORDEM_CLASSES,
        ordered=True
    )

    df_filtrado = df_filtrado.sort_values(["classe", "produto"])

    if df_filtrado.empty:
        st.warning("Nenhuma informação encontrada com os filtros selecionados.")
    else:
        for _, row in df_filtrado.iterrows():
            with st.container():
                st.markdown(f"### 📦 {row['produto']}")
                st.write(f"**Classe:** {row['classe']}")
                st.write(f"**Informações:** {row['informacoes']}")

                data_txt = ""
                if "data_atualizacao" in row and pd.notnull(row["data_atualizacao"]):
                    data_txt = row["data_atualizacao"].strftime("%d/%m/%Y")

                st.caption(
                    f"Atualizado por: {row.get('atualizado_por', '')} "
                    f"({row.get('nivel_usuario', '')}) "
                    f"| Data: {data_txt} "
                    f"| Hora: {row.get('hora_atualizacao', '')}"
                )

                st.divider()

    st.subheader("📥 Exportação")

    if st.button("📄 Gerar PDF - Sobre os Produtos"):
        try:
            nome_pdf = f"sobre_produtos_{datetime.now().strftime('%d-%m-%Y')}.pdf"

            gerar_pdf_sobre_produtos(df_filtrado, nome_pdf)

            with open(nome_pdf, "rb") as f:
                st.download_button(
                    "📥 Baixar PDF - Sobre os Produtos",
                    f,
                    file_name=nome_pdf
                )

            registrar_acao(
                supabase,
                "PDF gerado",
                "Sobre os Produtos",
                "PDF das informações dos produtos gerado"
            )

        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
