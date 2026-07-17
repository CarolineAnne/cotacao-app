import io
from datetime import datetime

import streamlit as st
import pandas as pd


def registrar(registrar_acao_func, acao, tela="Solicitações", detalhes="", arquivo_url=""):
    if registrar_acao_func:
        try:
            registrar_acao_func(acao, tela, detalhes, arquivo_url)
        except TypeError:
            try:
                registrar_acao_func(acao, tela, detalhes)
            except Exception:
                pass
        except Exception:
            pass


def carregar_tipos_solicitacao(supabase):
    resp = (
        supabase
        .table("tipos_solicitacao")
        .select("*")
        .order("nome")
        .execute()
    )

    return pd.DataFrame(resp.data or [])


def carregar_solicitacoes(supabase):
    resp = (
        supabase
        .table("solicitacoes")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    return pd.DataFrame(resp.data or [])


def formatar_data_coluna(df, coluna="data"):
    df = df.copy()

    if coluna in df.columns:
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce").dt.strftime("%d/%m/%Y")

    return df


def tela_solicitacoes(supabase, nivel, registrar_acao_func=None):
    st.title("📄 Solicitações")

    st.info(
        "Use as abas abaixo para cadastrar tipos, enviar solicitações, acompanhar registros "
        "e anexar ou baixar PDFs."
    )

    aba_tipos, aba_nova, aba_lista, aba_detalhes = st.tabs([
        "➕ Tipos de Solicitação",
        "📝 Nova Solicitação",
        "📋 Solicitações Registradas",
        "🔎 Detalhes / PDF"
    ])

    # =========================================================
    # ABA 1 - TIPOS DE SOLICITAÇÃO
    # =========================================================
    with aba_tipos:
        st.subheader("➕ Tipos de Solicitação")

        if nivel != "admin":
            st.warning("Apenas administradores podem cadastrar tipos de solicitação.")
        else:
            with st.form("form_cadastrar_tipo_solicitacao"):
                novo_tipo = st.text_input("Novo tipo de solicitação")
                cadastrar_tipo = st.form_submit_button("Cadastrar Tipo")

            if cadastrar_tipo:
                tipo_limpo = str(novo_tipo or "").strip()

                if not tipo_limpo:
                    st.warning("Digite um nome para o tipo.")
                else:
                    try:
                        tipos_df = carregar_tipos_solicitacao(supabase)

                        if not tipos_df.empty and "nome" in tipos_df.columns:
                            existe = tipos_df["nome"].astype(str).str.lower().eq(tipo_limpo.lower()).any()
                        else:
                            existe = False

                        if existe:
                            st.error("Este tipo de solicitação já está cadastrado.")
                        else:
                            supabase.table("tipos_solicitacao").insert({
                                "nome": tipo_limpo
                            }).execute()

                            st.success("Tipo cadastrado com sucesso!")

                            registrar(
                                registrar_acao_func,
                                "Cadastro de tipo de solicitação",
                                detalhes=f"Tipo cadastrado: {tipo_limpo}"
                            )

                            st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao cadastrar tipo: {e}")

        st.divider()
        st.markdown("#### Tipos cadastrados")

        try:
            tipos_df = carregar_tipos_solicitacao(supabase)

            if tipos_df.empty:
                st.info("Nenhum tipo de solicitação cadastrado.")
            else:
                st.dataframe(
                    tipos_df,
                    width="stretch",
                    hide_index=True
                )

        except Exception as e:
            st.error(f"Erro ao carregar tipos: {e}")

    # =========================================================
    # ABA 2 - NOVA SOLICITAÇÃO
    # =========================================================
    with aba_nova:
        st.subheader("📝 Nova Solicitação")

        if nivel != "requisitante":
            st.warning("Apenas usuários requisitantes podem enviar novas solicitações.")
        else:
            try:
                tipos_df = carregar_tipos_solicitacao(supabase)

                if tipos_df.empty:
                    st.warning("Nenhum tipo de solicitação cadastrado. Peça ao administrador para cadastrar um tipo.")
                    tipos_lista = []
                else:
                    tipos_lista = tipos_df["nome"].astype(str).tolist()

            except Exception as e:
                st.error(f"Erro ao carregar tipos: {e}")
                tipos_lista = []

            if tipos_lista:
                with st.form("form_nova_solicitacao"):
                    tipo = st.selectbox(
                        "Tipo de solicitação",
                        tipos_lista
                    )

                    descricao = st.text_area(
                        "Descrição da solicitação",
                        height=160
                    )

                    enviar = st.form_submit_button("Enviar Solicitação")

                if enviar:
                    descricao_limpa = str(descricao or "").strip()

                    if not descricao_limpa:
                        st.warning("Descreva a solicitação antes de enviar.")
                    else:
                        try:
                            supabase.table("solicitacoes").insert({
                                "data": datetime.now().strftime("%Y-%m-%d"),
                                "usuario": st.session_state.get("nome", ""),
                                "tipo": tipo,
                                "descricao": descricao_limpa,
                                "status": "Pendente",
                                "arquivo_url": ""
                            }).execute()

                            st.success("Solicitação enviada com sucesso!")

                            registrar(
                                registrar_acao_func,
                                "Solicitação enviada",
                                detalhes=f"Tipo: {tipo} | Descrição: {descricao_limpa}"
                            )

                            st.rerun()

                        except Exception as e:
                            st.error(f"Erro ao enviar solicitação: {e}")

    # =========================================================
    # ABA 3 - LISTAGEM
    # =========================================================
    with aba_lista:
        st.subheader("📋 Solicitações Registradas")

        try:
            df_sol = carregar_solicitacoes(supabase)

        except Exception as e:
            st.error(f"Erro ao carregar solicitações: {e}")
            return

        if df_sol.empty:
            st.info("Nenhuma solicitação registrada.")
        else:
            df_filtro = df_sol.copy()

            if "data" in df_filtro.columns:
                df_filtro["data"] = pd.to_datetime(df_filtro["data"], errors="coerce")

            col1, col2, col3 = st.columns(3)

            with col1:
                status_lista = ["Todos"] + sorted(df_filtro["status"].dropna().astype(str).unique().tolist())
                status_sel = st.selectbox("Status", status_lista, key="filtro_status_solicitacoes")

            with col2:
                tipo_lista = ["Todos"] + sorted(df_filtro["tipo"].dropna().astype(str).unique().tolist())
                tipo_sel = st.selectbox("Tipo", tipo_lista, key="filtro_tipo_solicitacoes")

            with col3:
                usuarios_lista = ["Todos"] + sorted(df_filtro["usuario"].dropna().astype(str).unique().tolist())
                usuario_sel = st.selectbox("Usuário", usuarios_lista, key="filtro_usuario_solicitacoes")

            if status_sel != "Todos":
                df_filtro = df_filtro[df_filtro["status"].astype(str) == status_sel]

            if tipo_sel != "Todos":
                df_filtro = df_filtro[df_filtro["tipo"].astype(str) == tipo_sel]

            if usuario_sel != "Todos":
                df_filtro = df_filtro[df_filtro["usuario"].astype(str) == usuario_sel]

            colm1, colm2, colm3 = st.columns(3)

            colm1.metric("Total", len(df_filtro))

            if "status" in df_filtro.columns:
                pendentes = len(df_filtro[df_filtro["status"].astype(str).str.lower() == "pendente"])
                concluidas = len(df_filtro[df_filtro["status"].astype(str).str.lower() == "concluído"])
            else:
                pendentes = 0
                concluidas = 0

            colm2.metric("Pendentes", pendentes)
            colm3.metric("Concluídas", concluidas)

            df_tabela = formatar_data_coluna(df_filtro, "data")

            st.dataframe(
                df_tabela,
                width="stretch",
                hide_index=True
            )

            st.divider()

            try:
                buffer = io.BytesIO()
                df_tabela.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)

                st.download_button(
                    "📥 Exportar Solicitações em Excel",
                    buffer,
                    file_name=f"solicitacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")

    # =========================================================
    # ABA 4 - DETALHES / PDF
    # =========================================================
    with aba_detalhes:
        st.subheader("🔎 Detalhes da Solicitação")

        try:
            df_sol = carregar_solicitacoes(supabase)

        except Exception as e:
            st.error(f"Erro ao carregar solicitações: {e}")
            return

        if df_sol.empty:
            st.info("Nenhuma solicitação registrada.")
            return

        ids = df_sol["id"].tolist()

        id_selecionado = st.selectbox(
            "Selecione a solicitação",
            ids,
            key="select_solicitacao_detalhes"
        )

        dados = df_sol[df_sol["id"] == id_selecionado].iloc[0]

        data_txt = ""
        try:
            data_txt = pd.to_datetime(dados.get("data"), errors="coerce").strftime("%d/%m/%Y")
        except Exception:
            data_txt = str(dados.get("data", ""))

        st.markdown("#### Informações da solicitação")

        col1, col2, col3 = st.columns(3)

        col1.write(f"**ID:** {dados.get('id', '')}")
        col2.write(f"**Data:** {data_txt}")
        col3.write(f"**Status:** {dados.get('status', '')}")

        st.write(f"**Usuário:** {dados.get('usuario', '')}")
        st.write(f"**Tipo:** {dados.get('tipo', '')}")
        st.write(f"**Descrição:** {dados.get('descricao', '')}")

        arquivo_url = str(dados.get("arquivo_url", "") or "").strip()

        st.divider()
        st.markdown("#### Arquivo PDF")

        if arquivo_url:
            st.markdown(f"[📥 Baixar PDF]({arquivo_url})")
        else:
            st.info("Ainda não há PDF anexado para esta solicitação.")

        if nivel == "admin":
            st.divider()
            st.markdown("#### Ações do Administrador")

            arquivo_pdf = st.file_uploader(
                "Anexar PDF",
                type=["pdf"],
                key=f"pdf_solicitacao_{id_selecionado}"
            )

            if arquivo_pdf is not None:
                if st.button("Enviar PDF e Marcar como Concluído", key="btn_enviar_pdf_solicitacao"):
                    try:
                        nome_arquivo = f"solicitacao_{id_selecionado}.pdf"

                        supabase.storage.from_("arquivos").upload(
                            nome_arquivo,
                            arquivo_pdf.getvalue(),
                            {
                                "content-type": "application/pdf",
                                "upsert": "true"
                            }
                        )

                        url_pdf = supabase.storage.from_("arquivos").get_public_url(nome_arquivo)

                        supabase.table("solicitacoes").update({
                            "arquivo_url": url_pdf,
                            "status": "Concluído"
                        }).eq("id", int(id_selecionado)).execute()

                        registrar(
                            registrar_acao_func,
                            "PDF anexado",
                            detalhes=f"PDF anexado à solicitação ID {id_selecionado}",
                            arquivo_url=url_pdf
                        )

                        st.success("PDF anexado e solicitação marcada como concluída!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao anexar PDF: {e}")

            col_admin1, col_admin2 = st.columns(2)

            with col_admin1:
                if st.button("✅ Marcar como Concluído sem PDF", key="btn_concluir_sem_pdf"):
                    try:
                        supabase.table("solicitacoes").update({
                            "status": "Concluído"
                        }).eq("id", int(id_selecionado)).execute()

                        registrar(
                            registrar_acao_func,
                            "Solicitação concluída",
                            detalhes=f"Solicitação ID {id_selecionado} marcada como concluída sem PDF"
                        )

                        st.success("Solicitação marcada como concluída!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao atualizar status: {e}")

            with col_admin2:
                if st.button("↩️ Marcar como Pendente", key="btn_marcar_pendente"):
                    try:
                        supabase.table("solicitacoes").update({
                            "status": "Pendente"
                        }).eq("id", int(id_selecionado)).execute()

                        registrar(
                            registrar_acao_func,
                            "Solicitação reaberta",
                            detalhes=f"Solicitação ID {id_selecionado} marcada como pendente"
                        )

                        st.success("Solicitação marcada como pendente.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao atualizar status: {e}")
