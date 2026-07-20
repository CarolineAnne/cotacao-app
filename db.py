import streamlit as st
from supabase import create_client


def ler_config_supabase(secrets):
    try:
        url = str(secrets.get("SUPABASE_URL", "") or "").strip()
        key = str(secrets.get("SUPABASE_KEY", "") or "").strip()
    except Exception as erro:
        raise ValueError(
            "Configuração do Supabase não encontrada. "
            "Crie o arquivo .streamlit/secrets.toml com SUPABASE_URL e SUPABASE_KEY."
        ) from erro

    faltando = []

    if not url:
        faltando.append("SUPABASE_URL")

    if not key:
        faltando.append("SUPABASE_KEY")

    if faltando:
        nomes = ", ".join(faltando)
        raise ValueError(
            "Configuração do Supabase incompleta. "
            f"Informe {nomes} no arquivo .streamlit/secrets.toml."
        )

    return url, key


@st.cache_resource
def conectar_supabase():
    try:
        url, key = ler_config_supabase(st.secrets)
    except ValueError as erro:
        st.error(str(erro))
        st.info(
            "Esse arquivo é local e não deve ser enviado ao Git. "
            "Use o modelo indicado no README."
        )
        st.stop()

    try:
        return create_client(url, key)
    except Exception:
        st.error(
            "Não foi possível iniciar a conexão com o Supabase. "
            "Confira se SUPABASE_URL e SUPABASE_KEY estão corretos."
        )
        st.stop()
