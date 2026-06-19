import streamlit as st
import pandas as pd

from utils import corrigir_classe


CLASSES_PRODUTO = ["Hortaliças", "Frutas", "Especiarias", "Cereais"]
UNIDADES_PRODUTO = ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Cento", "Fd"]
ORDEM_CLASSES = {classe: i for i, classe in enumerate(CLASSES_PRODUTO, start=1)}
ORDEM_CLASSES["SEM CLASSE"] = 99


def indice_seguro(lista, valor, padrao=0):
    try:
        return lista.index(valor)
    except Exception:
        return padrao


def registrar(registrar_acao_func, acao, tela="Cadastro de Produtos", detalhes=""):
    if registrar_acao_func:
        try:
            registrar_acao_func(acao, tela, detalhes)
        except Exception:
            pass


def carregar_produtos_admin(supabase):
    resp = supabase.table("produtos").select("*").execute()
    df = pd.DataFrame(resp.data or [])

    if df.empty:
        return df

    df["nome"] = df["nome"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)
    df["ordem_classe"] = df["classe"].map(ORDEM_CLASSES).fillna(99)
    df = df.sort_values(["ordem_classe", "nome"])
    df = df.drop(columns=["ordem_classe"], errors="ignore")

    return df


def produto_existe(supabase, nome, ignorar_id=None):
    nome = str(nome or "").strip().upper()

    if not nome:
        return False

    resp = (
        supabase
        .table("produtos")
        .select("id, nome")
        .eq("nome", nome)
        .execute()
    )

    dados = resp.data or []

    if ignorar_id is not None:
        dados = [d for d in dados if int(d.get("id", 0)) != int(ignorar_id)]

    return len(dados) > 0


def tela_cadastro_produtos(supabase, registrar_acao_func=None):
    st.title("📦 Cadastro de Produtos")

    st.info("Use as abas abaixo para cadastrar, consultar ou editar produtos.")

    try:
        df = carregar_produtos_admin(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        return

    aba_cadastro, aba_lista, aba_edicao = st.tabs([
        "➕ Cadastrar Produto",
        "📋 Produtos Cadastrados",
        "✏️ Editar / Excluir"
    ])

    # =========================================================
    # ABA 1 - CADASTRAR PRODUTO
    # =========================================================
    with aba_cadastro:
        st.subheader("➕ Novo Produto")

        with st.form("form_cadastrar_produto"):
            nome = st.text_input("Nome")

            classe = st.selectbox(
                "Classe",
                CLASSES_PRODUTO
            )

            unidade = st.selectbox(
                "Unidade",
                UNIDADES_PRODUTO
            )

            kg = st.number_input(
                "Kg",
                min_value=0,
                step=1,
                format="%d"
            )

            cadastrar = st.form_submit_button("Cadastrar Produto")

        if cadastrar:
            nome_limpo = str(nome or "").strip().upper()

            if not nome_limpo:
                st.warning("Informe o nome do produto.")
            elif float(kg) <= 0:
                st.warning("Informe o peso em kg do produto. O valor precisa ser maior que zero.")
            elif produto_existe(supabase, nome_limpo):
                st.error("Este produto já está cadastrado.")
            else:
                try:
                    supabase.table("produtos").insert({
                        "nome": nome_limpo,
                        "classe": corrigir_classe(classe),
                        "unidade": unidade,
                        "kg": int(kg)
                    }).execute()

                    st.success("Produto cadastrado com sucesso!")
                    st.cache_data.clear()

                    registrar(
                        registrar_acao_func,
                        "Cadastro de produto",
                        detalhes=f"Produto cadastrado: {nome_limpo} | Classe: {classe}"
                    )

                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao cadastrar produto: {e}")

    # =========================================================
    # ABA 2 - LISTAGEM DE PRODUTOS
    # =========================================================
    with aba_lista:
        st.subheader("📋 Produtos cadastrados")

        if df.empty:
            st.info("Nenhum produto cadastrado.")
        else:
            col1, col2, col3 = st.columns(3)

            col1.metric("Total de produtos", len(df))
            col2.metric("Classes", df["classe"].nunique())
            col3.metric("Unidades", df["unidade"].nunique() if "unidade" in df.columns else 0)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

    # =========================================================
    # ABA 3 - EDITAR / EXCLUIR PRODUTO
    # =========================================================
    with aba_edicao:
        st.subheader("✏️ Editar / Excluir Produto")

        if df.empty:
            st.info("Nenhum produto cadastrado para editar.")
            return

        produto_selecionado = st.selectbox(
            "Produto",
            df["nome"].astype(str).tolist(),
            key="select_prod_modular"
        )

        dados = df[df["nome"].astype(str) == str(produto_selecionado)].iloc[0]
        id_produto = int(dados["id"])

        if "produto_edicao_anterior" not in st.session_state:
            st.session_state.produto_edicao_anterior = None

        if st.session_state.produto_edicao_anterior != produto_selecionado:
            st.session_state.edit_prod_nome_modular = str(dados.get("nome", ""))

            classe_banco = corrigir_classe(str(dados.get("classe", "")))
            if classe_banco not in CLASSES_PRODUTO:
                classe_banco = CLASSES_PRODUTO[0]

            unidade_banco = str(dados.get("unidade", "Kg"))
            if unidade_banco not in UNIDADES_PRODUTO:
                unidade_banco = "Kg"

            try:
                kg_banco = int(float(dados.get("kg", 0)))
            except Exception:
                kg_banco = 0

            st.session_state.edit_classe_modular = classe_banco
            st.session_state.edit_unidade_modular = unidade_banco
            st.session_state.edit_kg_modular = kg_banco
            st.session_state.produto_edicao_anterior = produto_selecionado

        novo_nome = st.text_input("Nome", key="edit_prod_nome_modular")

        nova_classe = st.selectbox(
            "Classe",
            CLASSES_PRODUTO,
            index=indice_seguro(
                CLASSES_PRODUTO,
                st.session_state.get("edit_classe_modular", CLASSES_PRODUTO[0])
            ),
            key="edit_classe_modular"
        )

        nova_unidade = st.selectbox(
            "Unidade",
            UNIDADES_PRODUTO,
            index=indice_seguro(
                UNIDADES_PRODUTO,
                st.session_state.get("edit_unidade_modular", "Kg")
            ),
            key="edit_unidade_modular"
        )

        novo_kg = st.number_input(
            "Kg",
            min_value=0,
            step=1,
            format="%d",
            key="edit_kg_modular"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Atualizar produto")

            if st.button("✏️ Atualizar Produto", key="btn_atualizar_produto_modular"):
                novo_nome_limpo = str(novo_nome or "").strip().upper()
                nome_antigo = str(dados.get("nome", "")).strip().upper()

                if not novo_nome_limpo:
                    st.warning("Informe o nome do produto.")
                elif float(novo_kg) <= 0:
                    st.warning("Informe o peso em kg do produto. O valor precisa ser maior que zero.")
                elif produto_existe(supabase, novo_nome_limpo, ignorar_id=id_produto):
                    st.error("Já existe outro produto cadastrado com esse nome.")
                else:
                    try:
                        supabase.table("produtos").update({
                            "nome": novo_nome_limpo,
                            "classe": corrigir_classe(nova_classe),
                            "unidade": nova_unidade,
                            "kg": int(novo_kg)
                        }).eq("id", id_produto).execute()

                        if nome_antigo != novo_nome_limpo:
                            supabase.table("cotacoes")\
                                .update({"produto": novo_nome_limpo})\
                                .eq("produto", nome_antigo)\
                                .execute()

                        st.success("Produto atualizado com sucesso!")
                        st.cache_data.clear()

                        registrar(
                            registrar_acao_func,
                            "Atualização de produto",
                            detalhes=f"Produto alterado de {nome_antigo} para {novo_nome_limpo}"
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao atualizar produto: {e}")

        with col2:
            st.markdown("#### Excluir produto")

            confirmar = st.checkbox(
                "Confirmo que desejo excluir este produto e suas cotações",
                key=f"confirmar_excluir_produto_{id_produto}"
            )

            if st.button("🗑️ Excluir Produto", key="btn_excluir_produto_modular"):
                if not confirmar:
                    st.warning("Marque a confirmação antes de excluir.")
                else:
                    try:
                        nome_antigo = str(dados.get("nome", "")).strip().upper()

                        supabase.table("cotacoes")\
                            .delete()\
                            .eq("produto", nome_antigo)\
                            .execute()

                        supabase.table("produtos")\
                            .delete()\
                            .eq("id", id_produto)\
                            .execute()

                        st.success("Produto excluído com sucesso!")
                        st.cache_data.clear()

                        registrar(
                            registrar_acao_func,
                            "Exclusão de produto",
                            detalhes=f"Produto excluído: {nome_antigo}"
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao excluir produto: {e}")
