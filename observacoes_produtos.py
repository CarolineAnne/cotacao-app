import streamlit as st
import pandas as pd

from datetime import datetime

from dados_utils import carregar_produtos
from utils import corrigir_classe, data_hoje_brasil


def buscar_observacao_produto(supabase, produto, data_ref):
    try:
        data_str = data_ref.strftime("%Y-%m-%d")

        resp = (
            supabase
            .table("observacoes_produtos")
            .select("*")
            .eq("produto", produto)
            .eq("data_ref", data_str)
            .limit(1)
            .execute()
        )

        if resp.data:
            return resp.data[0]

        return None

    except Exception as e:
        st.error(f"Erro ao buscar observação: {e}")
        return None


def carregar_observacoes_produto_periodo(supabase, produto, data_inicial, data_final):
    try:
        resp = (
            supabase
            .table("observacoes_produtos")
            .select("*")
            .eq("produto", produto)
            .gte("data_ref", data_inicial.strftime("%Y-%m-%d"))
            .lte("data_ref", data_final.strftime("%Y-%m-%d"))
            .order("data_ref", desc=False)
            .execute()
        )

        df = pd.DataFrame(resp.data or [])

        if not df.empty:
            df["data_ref"] = pd.to_datetime(df["data_ref"], errors="coerce")
            df["produto"] = df["produto"].astype(str).str.strip().str.upper()
            df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

        return df

    except Exception:
        return pd.DataFrame()


def salvar_observacao_produto(supabase, produto, classe, data_ref, observacao):
    data_str = data_ref.strftime("%Y-%m-%d")

    dados = {
        "data_ref": data_str,
        "produto": produto.strip().upper(),
        "classe": corrigir_classe(classe),
        "observacao": observacao.strip(),
        "criado_por": st.session_state.get("nome", ""),
        "atualizado_em": datetime.now().isoformat()
    }

    (
        supabase
        .table("observacoes_produtos")
        .upsert(dados, on_conflict="data_ref,produto")
        .execute()
    )

def carregar_observacoes_periodo(supabase, data_inicial, data_final, produto=None):
    try:
        query = (
            supabase
            .table("observacoes_produtos")
            .select("*")
            .gte("data_ref", data_inicial.strftime("%Y-%m-%d"))
            .lte("data_ref", data_final.strftime("%Y-%m-%d"))
            .order("data_ref", desc=False)
        )

        if produto and produto != "Todos":
            query = query.eq("produto", produto)

        resp = query.execute()

        df = pd.DataFrame(resp.data or [])

        if not df.empty:
            df["data_ref"] = pd.to_datetime(df["data_ref"], errors="coerce")
            df["produto"] = df["produto"].astype(str).str.strip().str.upper()
            df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

        return df

    except Exception as e:
        st.error(f"Erro ao carregar observações do período: {e}")
        return pd.DataFrame()

def tela_observacoes_produtos(supabase):
    st.title("📝 Observações dos Produtos")

    st.info(
        "Nesta tela você pode registrar observações sobre produtos. "
        "Essas observações poderão aparecer nos relatórios analíticos."
    )

    produtos = carregar_produtos(supabase)

    if produtos.empty:
        st.warning("Nenhum produto cadastrado.")
        return

    produtos = produtos.copy()
    produtos["nome"] = produtos["nome"].astype(str).str.strip().str.upper()
    produtos["classe"] = produtos["classe"].astype(str).str.strip().apply(corrigir_classe)

    produtos = produtos.sort_values(["classe", "nome"])

    st.subheader("➕ Cadastrar ou atualizar observação")

    col1, col2 = st.columns(2)

    with col1:
        produto_sel = st.selectbox(
            "Produto",
            produtos["nome"].tolist(),
            key="obs_produto_sel"
        )

    dados_produto = produtos[produtos["nome"] == produto_sel].iloc[0]
    classe_produto = dados_produto["classe"]

    with col2:
        data_ref = st.date_input(
            "Data da observação",
            value=data_hoje_brasil(),
            key="obs_data_ref"
        )

    observacao_existente = buscar_observacao_produto(
        supabase,
        produto_sel,
        data_ref
    )

    texto_atual = ""

    if observacao_existente:
        texto_atual = str(observacao_existente.get("observacao", ""))

    st.write(f"**Classe:** {classe_produto}")

    observacao = st.text_area(
        "Observação",
        value=texto_atual,
        height=160,
        placeholder="Exemplo: aumento associado à baixa oferta, sazonalidade, custo de produção, qualidade do produto ou relato dos permissionários.",
        key="obs_texto_produto"
    )

    if st.button("💾 Salvar observação", type="primary"):
        if observacao.strip() == "":
            st.warning("Digite uma observação antes de salvar.")
        else:
            try:
                salvar_observacao_produto(
                    supabase=supabase,
                    produto=produto_sel,
                    classe=classe_produto,
                    data_ref=data_ref,
                    observacao=observacao
                )

                st.success("Observação salva com sucesso.")
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar observação: {e}")

    st.divider()

    st.subheader("📋 Observações registradas")

    col_data1, col_data2, col_prod = st.columns(3)

    with col_data1:
        data_inicial = st.date_input(
            "Data inicial",
            value=data_hoje_brasil(),
            key="obs_filtro_data_inicial"
        )

    with col_data2:
        data_final = st.date_input(
            "Data final",
            value=data_hoje_brasil(),
            key="obs_filtro_data_final"
        )

    with col_prod:
        produto_filtro = st.selectbox(
            "Filtrar produto",
            ["Todos"] + produtos["nome"].tolist(),
            key="obs_filtro_produto"
        )

    try:
        query = (
            supabase
            .table("observacoes_produtos")
            .select("*")
            .gte("data_ref", data_inicial.strftime("%Y-%m-%d"))
            .lte("data_ref", data_final.strftime("%Y-%m-%d"))
            .order("data_ref", desc=True)
        )

        if produto_filtro != "Todos":
            query = query.eq("produto", produto_filtro)

        resp = query.execute()

        df_obs = pd.DataFrame(resp.data or [])

    except Exception as e:
        st.error(f"Erro ao carregar observações: {e}")
        return

    if df_obs.empty:
        st.info("Nenhuma observação encontrada para os filtros selecionados.")
        return

    df_obs["data_ref"] = pd.to_datetime(
        df_obs["data_ref"],
        errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    colunas = [
        "data_ref",
        "produto",
        "classe",
        "observacao",
        "criado_por"
    ]

    colunas_existentes = [c for c in colunas if c in df_obs.columns]

    st.dataframe(
        df_obs[colunas_existentes],
        width="stretch"
    )