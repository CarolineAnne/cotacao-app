import streamlit as st
import pandas as pd

from auth_utils import gerar_hash_senha, senha_esta_com_hash


NIVEIS_USUARIO = ["admin", "cotacao", "requisitante"]


def indice_seguro(lista, valor, padrao=0):
    try:
        return lista.index(valor)
    except Exception:
        return padrao


def registrar(registrar_acao_func, acao, tela="Cadastro de Usuários", detalhes=""):
    if registrar_acao_func:
        try:
            registrar_acao_func(acao, tela, detalhes)
        except Exception:
            pass


def carregar_usuarios(supabase):
    resp = supabase.table("usuarios").select("*").order("nome").execute()
    return pd.DataFrame(resp.data or [])


def usuario_existe(supabase, usuario, ignorar_id=None):
    usuario = str(usuario or "").strip()

    if not usuario:
        return False

    resp = (
        supabase
        .table("usuarios")
        .select("id, usuario")
        .eq("usuario", usuario)
        .execute()
    )

    dados = resp.data or []

    if ignorar_id is not None:
        dados = [d for d in dados if int(d.get("id", 0)) != int(ignorar_id)]

    return len(dados) > 0


def preparar_tabela_usuarios(df):
    df_exibir = df.copy()

    if "senha" in df_exibir.columns:
        df_exibir["senha"] = df_exibir["senha"].apply(
            lambda s: "Protegida" if senha_esta_com_hash(s) else "Antiga - será protegida no próximo login"
        )

    return df_exibir


def tela_cadastro_usuarios(supabase, registrar_acao_func=None):
    st.title("👤 Cadastro de Usuários")

    st.info(
        "Use as abas abaixo para cadastrar, consultar ou editar usuários. "
        "As senhas são salvas de forma protegida. Ao editar um usuário, deixe o campo "
        "de nova senha em branco para manter a senha atual."
    )

    try:
        df = carregar_usuarios(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return

    aba_cadastro, aba_lista, aba_edicao = st.tabs([
        "➕ Cadastrar Usuário",
        "📋 Usuários Cadastrados",
        "✏️ Editar / Excluir"
    ])

    # =========================================================
    # ABA 1 - CADASTRAR USUÁRIO
    # =========================================================
    with aba_cadastro:
        st.subheader("➕ Novo Usuário")

        with st.form("form_cadastrar_usuario"):
            nome = st.text_input("Nome")
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            nivel = st.selectbox("Nível", NIVEIS_USUARIO)

            cadastrar = st.form_submit_button("Cadastrar Usuário")

        if cadastrar:
            nome_limpo = str(nome or "").strip()
            usuario_limpo = str(usuario or "").strip()
            senha_limpa = str(senha or "")

            if not nome_limpo:
                st.warning("Informe o nome do usuário.")
            elif not usuario_limpo:
                st.warning("Informe o usuário de acesso.")
            elif not senha_limpa:
                st.warning("Informe uma senha.")
            elif len(senha_limpa) < 4:
                st.warning("A senha precisa ter pelo menos 4 caracteres.")
            elif usuario_existe(supabase, usuario_limpo):
                st.error("Já existe um usuário cadastrado com esse login.")
            else:
                try:
                    senha_hash = gerar_hash_senha(senha_limpa)

                    supabase.table("usuarios").insert({
                        "nome": nome_limpo,
                        "usuario": usuario_limpo,
                        "senha": senha_hash,
                        "nivel": nivel
                    }).execute()

                    st.success("Usuário cadastrado com sucesso!")
                    st.cache_data.clear()

                    registrar(
                        registrar_acao_func,
                        "Cadastro de usuário",
                        detalhes=f"Usuário cadastrado: {usuario_limpo} | Nível: {nivel}"
                    )

                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao cadastrar usuário: {e}")

    # =========================================================
    # ABA 2 - LISTAGEM DE USUÁRIOS
    # =========================================================
    with aba_lista:
        st.subheader("📋 Usuários cadastrados")

        if df.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            df_exibir = preparar_tabela_usuarios(df)

            col1, col2, col3 = st.columns(3)

            col1.metric("Total de usuários", len(df_exibir))

            if "nivel" in df_exibir.columns:
                col2.metric("Níveis", df_exibir["nivel"].nunique())
                admins = len(df_exibir[df_exibir["nivel"].astype(str) == "admin"])
                col3.metric("Administradores", admins)
            else:
                col2.metric("Níveis", 0)
                col3.metric("Administradores", 0)

            st.dataframe(
                df_exibir,
                width="stretch",
                hide_index=True
            )

    # =========================================================
    # ABA 3 - EDITAR / EXCLUIR USUÁRIO
    # =========================================================
    with aba_edicao:
        st.subheader("✏️ Editar / Excluir Usuário")

        if df.empty:
            st.info("Nenhum usuário cadastrado para editar.")
            return

        usuarios_lista = df["usuario"].astype(str).tolist()

        usuario_sel = st.selectbox(
            "Selecione o usuário",
            usuarios_lista,
            key="select_user_modular"
        )

        dados = df[df["usuario"].astype(str) == str(usuario_sel)].iloc[0]
        id_usuario = int(dados["id"])

        if "usuario_edicao_anterior" not in st.session_state:
            st.session_state.usuario_edicao_anterior = None

        if st.session_state.usuario_edicao_anterior != usuario_sel:
            st.session_state.edit_user_nome_modular = str(dados.get("nome", ""))
            st.session_state.edit_user_usuario_modular = str(dados.get("usuario", ""))

            nivel_banco = str(dados.get("nivel", "requisitante"))

            if nivel_banco == "visitante":
                nivel_banco = "requisitante"

            if nivel_banco not in NIVEIS_USUARIO:
                nivel_banco = "requisitante"

            st.session_state.edit_user_nivel_modular = nivel_banco
            st.session_state.edit_user_senha_modular = ""
            st.session_state.usuario_edicao_anterior = usuario_sel

        novo_nome = st.text_input("Nome", key="edit_user_nome_modular")
        novo_usuario = st.text_input("Usuário", key="edit_user_usuario_modular")

        nova_senha = st.text_input(
            "Nova senha",
            type="password",
            placeholder="Deixe em branco para manter a senha atual",
            key="edit_user_senha_modular"
        )

        novo_nivel = st.selectbox(
            "Nível",
            NIVEIS_USUARIO,
            index=indice_seguro(
                NIVEIS_USUARIO,
                st.session_state.get("edit_user_nivel_modular", "requisitante")
            ),
            key="edit_user_nivel_modular"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Atualizar usuário")

            if st.button("✏️ Atualizar Usuário", key="btn_atualizar_usuario_modular"):
                nome_limpo = str(novo_nome or "").strip()
                usuario_limpo = str(novo_usuario or "").strip()
                senha_nova_limpa = str(nova_senha or "").strip()

                if not nome_limpo:
                    st.warning("Informe o nome do usuário.")
                elif not usuario_limpo:
                    st.warning("Informe o usuário de acesso.")
                elif usuario_existe(supabase, usuario_limpo, ignorar_id=id_usuario):
                    st.error("Já existe outro usuário com esse login.")
                elif senha_nova_limpa and len(senha_nova_limpa) < 4:
                    st.warning("A nova senha precisa ter pelo menos 4 caracteres.")
                else:
                    try:
                        dados_update = {
                            "nome": nome_limpo,
                            "usuario": usuario_limpo,
                            "nivel": novo_nivel
                        }

                        if senha_nova_limpa:
                            dados_update["senha"] = gerar_hash_senha(senha_nova_limpa)

                        supabase.table("usuarios").update(dados_update).eq("id", id_usuario).execute()

                        st.success("Usuário atualizado com sucesso!")
                        st.cache_data.clear()

                        registrar(
                            registrar_acao_func,
                            "Atualização de usuário",
                            detalhes=f"Usuário atualizado: {usuario_limpo} | Nível: {novo_nivel}"
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao atualizar usuário: {e}")

        with col2:
            st.markdown("#### Excluir usuário")

            usuario_logado = str(st.session_state.get("nome", "") or "")
            usuario_excluir = str(dados.get("usuario", "") or "")

            confirmar = st.checkbox(
                "Confirmo que desejo excluir este usuário",
                key=f"confirmar_excluir_usuario_{id_usuario}"
            )

            if st.button("🗑️ Excluir Usuário", key="btn_excluir_usuario_modular"):
                if not confirmar:
                    st.warning("Marque a confirmação antes de excluir.")
                else:
                    try:
                        usuario_excluido = str(dados.get("usuario", ""))

                        supabase.table("usuarios").delete().eq("id", id_usuario).execute()

                        st.success("Usuário excluído com sucesso!")
                        st.cache_data.clear()

                        registrar(
                            registrar_acao_func,
                            "Exclusão de usuário",
                            detalhes=f"Usuário excluído: {usuario_excluido}"
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao excluir usuário: {e}")
