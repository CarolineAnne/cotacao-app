import streamlit as st
import pandas as pd

from datetime import datetime

from auth_utils import verificar_login_seguro


@st.cache_data(ttl=60)
def carregar_produtos(_supabase):
    df = pd.DataFrame()

    try:
        resp = _supabase.table("produtos").select("*").execute()

        if resp and resp.data:
            df = pd.DataFrame(resp.data)

            df["nome"] = df["nome"].astype(str).str.strip().str.upper()
            df["classe"] = df["classe"].astype(str).str.strip()

    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")

    return df


@st.cache_data(ttl=60)
def carregar_todas_cotacoes(_supabase):
    todas = []
    inicio = 0
    passo = 1000

    colunas = (
        "id, data, classe, produto, unidade, kg, "
        "preco_min, preco_max, preco_medio, valor_kg, precos_digitados"
    )

    while True:
        resp = (
            _supabase
            .table("cotacoes")
            .select(colunas)
            .order("data", desc=False)
            .range(inicio, inicio + passo - 1)
            .execute()
        )

        dados = resp.data or []

        if not dados:
            break

        todas.extend(dados)

        if len(dados) < passo:
            break

        inicio += passo

    return pd.DataFrame(todas)


def contar_solicitacoes_pendentes(supabase):
    try:
        resp = (
            supabase
            .table("solicitacoes")
            .select("id")
            .eq("status", "Pendente")
            .execute()
        )

        return len(resp.data or [])

    except Exception:
        return 0


def verificar_login(supabase, usuario, senha):
    """
    Mantem compatibilidade com chamadas antigas usando o fluxo seguro.
    """
    return verificar_login_seguro(supabase, usuario, senha)


def registrar_acao(supabase, acao, tela="", detalhes="", arquivo_url=""):
    try:
        agora = datetime.now()

        supabase.table("acompanhamento").insert({
            "data": agora.strftime("%Y-%m-%d"),
            "hora": agora.strftime("%H:%M:%S"),
            "usuario": st.session_state.get("nome", ""),
            "nivel": st.session_state.get("nivel", ""),
            "tela": tela,
            "acao": acao,
            "detalhes": detalhes,
            "arquivo_url": arquivo_url
        }).execute()

    except Exception as e:
        st.error(f"Erro ao registrar ação: {e}")
