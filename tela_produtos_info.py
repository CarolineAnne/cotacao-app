import streamlit as st

from dados_utils import carregar_produtos
from produtos_info_utils import (
    carregar_info_produto,
    upload_foto_produto,
    salvar_info_produto
)


def tela_produtos_info(supabase):
    st.title("🍎 Informações dos Produtos")

    st.info(
        "Cadastre aqui as informações extras dos produtos, como descrição, "
        "vitaminas, minerais, benefícios, comportamento no Ceasa e foto."
    )

    # ================= CARREGAR PRODUTOS =================
    try:
        df_produtos = carregar_produtos(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        return

    if df_produtos.empty:
        st.warning("Nenhum produto cadastrado.")
        return

    df_produtos = df_produtos.copy()
    df_produtos["nome"] = df_produtos["nome"].astype(str).str.strip().str.upper()
    df_produtos["classe"] = df_produtos["classe"].astype(str).str.strip()
    df_produtos["unidade"] = df_produtos["unidade"].astype(str).str.strip()

    # ================= SELEÇÃO DO PRODUTO =================
    st.subheader("🔎 Selecionar produto")

    col1, col2 = st.columns(2)

    with col1:
        classes = ["Todas"] + sorted(df_produtos["classe"].dropna().unique().tolist())

        classe_sel = st.selectbox(
            "Classe",
            classes,
            key="info_produto_classe"
        )

    if classe_sel != "Todas":
        df_filtrado = df_produtos[df_produtos["classe"] == classe_sel].copy()
    else:
        df_filtrado = df_produtos.copy()

    with col2:
        produtos_lista = df_filtrado["nome"].dropna().unique().tolist()

        produto_sel = st.selectbox(
            "Produto",
            produtos_lista,
            key="info_produto_nome"
        )

    produto_row = df_filtrado[df_filtrado["nome"] == produto_sel].iloc[0]

    produto_id = int(produto_row["id"])
    produto_nome = produto_row["nome"]
    produto_classe = produto_row["classe"]
    produto_unidade = produto_row["unidade"]

    st.markdown("---")

    st.subheader("📌 Produto selecionado")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.metric("Produto", produto_nome)

    with col_b:
        st.metric("Classe", produto_classe)

    with col_c:
        st.metric("Unidade", produto_unidade)

    # ================= CARREGAR INFORMAÇÕES EXISTENTES =================
    try:
        info_existente = carregar_info_produto(supabase, produto_id)
    except Exception as e:
        st.error(str(e))
        return

    if info_existente is None:
        info_existente = {}

    st.markdown("---")

    # ================= CAMPOS DE TEXTO =================
    st.subheader("📝 Informações complementares")

    descricao_curta = st.text_area(
        "Descrição curta",
        value=info_existente.get("descricao_curta", "") or "",
        height=80,
        placeholder="Ex.: Produto bastante utilizado na culinária regional."
    )

    descricao_completa = st.text_area(
        "Descrição completa",
        value=info_existente.get("descricao_completa", "") or "",
        height=120
    )

    col1, col2 = st.columns(2)

    with col1:
        vitaminas = st.text_area(
            "Vitaminas",
            value=info_existente.get("vitaminas", "") or "",
            height=90,
            placeholder="Ex.: Vitamina C, vitaminas do complexo B"
        )

        minerais = st.text_area(
            "Minerais",
            value=info_existente.get("minerais", "") or "",
            height=90,
            placeholder="Ex.: Potássio, cálcio, magnésio, ferro"
        )

        beneficios = st.text_area(
            "Benefícios",
            value=info_existente.get("beneficios", "") or "",
            height=110,
            placeholder="Ex.: Fonte de fibras, baixo valor calórico."
        )

    with col2:
        informacao_nutricional = st.text_area(
            "Informação nutricional",
            value=info_existente.get("informacao_nutricional", "") or "",
            height=90
        )

        uso_culinario = st.text_area(
            "Uso culinário",
            value=info_existente.get("uso_culinario", "") or "",
            height=90,
            placeholder="Ex.: Usado em saladas, cozidos e pratos regionais."
        )

        sazonalidade = st.text_area(
            "Sazonalidade",
            value=info_existente.get("sazonalidade", "") or "",
            height=110,
            placeholder="Ex.: Pode apresentar maior oferta em períodos de safra."
        )

    comportamento_ceasa = st.text_area(
        "Comportamento no Ceasa",
        value=info_existente.get("comportamento_ceasa", "") or "",
        height=120,
        placeholder=(
            "Ex.: Produto com preço sensível à oferta local. "
            "Em períodos de menor entrada no mercado, pode apresentar aumento de preço."
        )
    )

    observacoes = st.text_area(
        "Observações",
        value=info_existente.get("observacoes", "") or "",
        height=90
    )

    st.markdown("---")

    # ================= FOTO =================
    st.subheader("🖼️ Foto do produto")

    foto_atual = info_existente.get("foto_url", "")

    if foto_atual:
        st.image(foto_atual, caption="Foto atual do produto", width=250)

    arquivo_foto = st.file_uploader(
        "Enviar nova foto",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"foto_produto_{produto_id}"
    )

    if arquivo_foto is not None:
        st.image(arquivo_foto, caption="Prévia da nova foto", width=250)

    st.markdown("---")

    # ================= SALVAR =================
    if st.button("💾 Salvar informações", type="primary"):
        try:
            foto_url = info_existente.get("foto_url", "")
            foto_path = info_existente.get("foto_path", "")

            if arquivo_foto is not None:
                foto_url, foto_path = upload_foto_produto(
                    supabase,
                    produto_id,
                    arquivo_foto
                )

            dados = {
                "produto_id": produto_id,
                "descricao_curta": descricao_curta,
                "descricao_completa": descricao_completa,
                "vitaminas": vitaminas,
                "minerais": minerais,
                "beneficios": beneficios,
                "informacao_nutricional": informacao_nutricional,
                "uso_culinario": uso_culinario,
                "sazonalidade": sazonalidade,
                "comportamento_ceasa": comportamento_ceasa,
                "observacoes": observacoes,
                "foto_url": foto_url,
                "foto_path": foto_path,
                "ativo": True
            }

            salvar_info_produto(supabase, dados)

            st.success("Informações salvas com sucesso.")
            st.rerun()

        except Exception as e:
            st.error(str(e))