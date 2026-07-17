import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from dados_utils import carregar_produtos, carregar_todas_cotacoes
from produtos_info_utils import carregar_info_produto
from graficos_utils import obter_estilo_linha, aplicar_estilo_impressao
from post_produto_posts import (
    calcular_indicadores_produto,
    criar_zip_posts,
    formatar_moeda,
    formatar_percentual,
    gerar_posts_produto_png,
    nome_arquivo_seguro,
    obter_campo,
)

# =========================================================
# TELA STREAMLIT
# =========================================================
def tela_post_produto_unitario(supabase):
    st.title("🥑 Post Unitário do Produto")

    st.info(
        "Agora o sistema gera dois posts: um com cotação e comportamento de preços, "
        "e outro com todas as informações cadastradas do produto."
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

    # ================= FILTROS =================
    st.subheader("🔎 Filtros")

    col1, col2 = st.columns(2)

    with col1:
        classes = sorted(df_produtos["classe"].dropna().unique().tolist())
        classe_sel = st.selectbox(
            "Classe",
            classes,
            key="unitario_classe"
        )

    df_filtrado = df_produtos[df_produtos["classe"] == classe_sel].copy()

    with col2:
        produtos_lista = sorted(df_filtrado["nome"].dropna().unique().tolist())
        produto_sel = st.selectbox(
            "Produto",
            produtos_lista,
            key="unitario_produto"
        )

    produto_row = df_filtrado[df_filtrado["nome"] == produto_sel].iloc[0]

    produto_id = int(produto_row["id"])
    produto_nome = produto_row["nome"]
    produto_classe = produto_row["classe"]
    produto_unidade = produto_row["unidade"]

    # ================= CARREGAR COTAÇÕES =================
    try:
        df_cotacoes = carregar_todas_cotacoes(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        return

    if df_cotacoes.empty:
        st.warning("Ainda não há cotações cadastradas.")
        return

    df_cotacoes = df_cotacoes.copy()
    df_cotacoes["data"] = pd.to_datetime(df_cotacoes["data"], errors="coerce")
    df_cotacoes = df_cotacoes.dropna(subset=["data"])

    df_cotacoes["produto"] = df_cotacoes["produto"].astype(str).str.strip().str.upper()
    df_cotacoes["valor_kg"] = pd.to_numeric(df_cotacoes["valor_kg"], errors="coerce").fillna(0)

    df_produto_total = df_cotacoes[
        df_cotacoes["produto"] == produto_nome
    ].copy()

    if df_produto_total.empty:
        st.warning("Não há cotações para esse produto.")
        return

    data_min = df_produto_total["data"].min().date()
    data_max = df_produto_total["data"].max().date()

    col3, col4 = st.columns(2)

    with col3:
        data_inicial = st.date_input(
            "Data inicial",
            value=data_min,
            min_value=data_min,
            max_value=data_max,
            key="unitario_data_inicial"
        )

    with col4:
        data_final = st.date_input(
            "Data final",
            value=data_max,
            min_value=data_min,
            max_value=data_max,
            key="unitario_data_final"
        )

    if data_inicial > data_final:
        st.warning("A data inicial não pode ser maior que a data final.")
        return

    df_periodo = df_produto_total[
        (df_produto_total["data"].dt.date >= data_inicial) &
        (df_produto_total["data"].dt.date <= data_final)
    ].copy()

    df_periodo = df_periodo[df_periodo["valor_kg"] > 0].copy()

    if df_periodo.empty:
        st.warning("Não há preços válidos para esse produto no período escolhido.")
        return

    # ================= INFORMAÇÕES DO PRODUTO =================
    try:
        info_produto = carregar_info_produto(supabase, produto_id)
    except Exception as e:
        st.error(str(e))
        return

    if info_produto is None:
        info_produto = {}

    indicadores = calcular_indicadores_produto(df_periodo)

    if indicadores is None:
        st.warning("Não foi possível calcular os indicadores.")
        return

    st.markdown("---")

    # ================= PRÉVIA =================
    st.subheader("📌 Prévia da análise do produto")

    col_img, col_info = st.columns([1, 2])

    with col_img:
        foto_url = info_produto.get("foto_url", "")

        if foto_url:
            st.image(foto_url, caption=produto_nome, use_container_width=True)
        else:
            st.warning("Produto sem foto cadastrada.")

    with col_info:
        st.markdown(f"### {produto_nome}")
        st.write(f"**Classe:** {produto_classe}")
        st.write(f"**Unidade:** {produto_unidade}")
        st.write(f"**Descrição curta:** {obter_campo(info_produto, 'descricao_curta')}")

    st.markdown("---")

    st.subheader("📊 Indicadores do período")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Preço médio/kg", formatar_moeda(indicadores["preco_medio"]))
    c2.metric("Menor preço/kg", formatar_moeda(indicadores["preco_minimo"]))
    c3.metric("Maior preço/kg", formatar_moeda(indicadores["preco_maximo"]))
    c4.metric("Variação", formatar_percentual(indicadores["variacao"]))

    st.markdown("---")

    st.subheader("📈 Comportamento dos preços no período")

    df_grafico = (
        df_periodo
        .groupby("data", as_index=False)
        .agg(valor_kg=("valor_kg", "mean"))
        .sort_values("data")
    )

    marcador, estilo_linha = obter_estilo_linha(0)

    figura_grafico, eixo_grafico = plt.subplots(figsize=(10, 4.5))

    eixo_grafico.plot(
        df_grafico["data"],
        df_grafico["valor_kg"],
        color="black",
        linestyle=estilo_linha,
        marker=marcador,
        linewidth=2.2,
        markersize=7,
        markerfacecolor="white",
        markeredgecolor="black",
        markeredgewidth=1.2,
        label="Preço por kg"
    )

    media_periodo_tela = df_grafico["valor_kg"].mean()

    eixo_grafico.axhline(
        media_periodo_tela,
        color="black",
        linestyle="--",
        linewidth=1.3,
        label="Média do período"
    )

    eixo_grafico.set_title(f"Comportamento dos preços - {produto_nome}")
    eixo_grafico.set_xlabel("Data")
    eixo_grafico.set_ylabel("Preço por kg (R$)")

    aplicar_estilo_impressao(eixo_grafico)

    eixo_grafico.legend(
        loc="best",
        frameon=True,
        edgecolor="black"
    )

    eixo_grafico.xaxis.set_major_locator(mdates.AutoDateLocator())
    eixo_grafico.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

    figura_grafico.autofmt_xdate()
    figura_grafico.tight_layout()

    st.pyplot(figura_grafico)
    plt.close(figura_grafico)

    st.markdown("---")

    st.subheader("🥗 Informações cadastradas do produto")

    col_nutri, col_ceasa = st.columns(2)

    with col_nutri:
        st.markdown("#### Nutrição")
        st.write("**Vitaminas:**")
        st.write(obter_campo(info_produto, "vitaminas"))

        st.write("**Minerais:**")
        st.write(obter_campo(info_produto, "minerais"))

        st.write("**Benefícios:**")
        st.write(obter_campo(info_produto, "beneficios"))

        st.write("**Informação nutricional:**")
        st.write(obter_campo(info_produto, "informacao_nutricional"))

    with col_ceasa:
        st.markdown("#### Mercado e uso")
        st.write("**Uso culinário:**")
        st.write(obter_campo(info_produto, "uso_culinario"))

        st.write("**Sazonalidade:**")
        st.write(obter_campo(info_produto, "sazonalidade"))

        st.write("**Comportamento no Ceasa:**")
        st.write(obter_campo(info_produto, "comportamento_ceasa"))

        st.write("**Observações:**")
        st.write(obter_campo(info_produto, "observacoes"))

    st.markdown("---")

    if st.button("🖼️ Gerar dois posts do produto", type="primary"):
        try:
            post_1_png, post_2_png = gerar_posts_produto_png(
                produto_nome=produto_nome,
                produto_classe=produto_classe,
                produto_unidade=produto_unidade,
                data_inicial=data_inicial,
                data_final=data_final,
                info_produto=info_produto,
                indicadores=indicadores,
                df_periodo=df_periodo
            )

            posts_zip = criar_zip_posts(
                produto_nome,
                post_1_png,
                post_2_png
            )

            st.success("Dois posts gerados com sucesso.")

            st.subheader("Post 1 - Cotação e comportamento de preços")
            st.image(post_1_png, caption="Post 1 - Cotação", use_container_width=True)

            st.download_button(
                "⬇️ Baixar Post 1 - Cotação",
                data=post_1_png,
                file_name=f"{nome_arquivo_seguro(produto_nome)}_post_1_cotacao.png",
                mime="image/png"
            )

            st.subheader("Post 2 - Informações do produto")
            st.image(post_2_png, caption="Post 2 - Informações", use_container_width=True)

            st.download_button(
                "⬇️ Baixar Post 2 - Informações",
                data=post_2_png,
                file_name=f"{nome_arquivo_seguro(produto_nome)}_post_2_informacoes.png",
                mime="image/png"
            )

            st.download_button(
                "📦 Baixar os dois posts em ZIP",
                data=posts_zip,
                file_name=f"{nome_arquivo_seguro(produto_nome)}_posts.zip",
                mime="application/zip"
            )

        except Exception as e:
            st.error(f"Erro ao gerar os posts: {e}")
