import os
import streamlit as st
import pandas as pd
import textwrap
import tempfile
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from io import BytesIO
from PIL import Image
from datetime import datetime

from dados_utils import carregar_produtos, carregar_todas_cotacoes
from produtos_info_utils import carregar_info_produto
from graficos_utils import (
    obter_estilo_linha,
    aplicar_estilo_impressao
)


def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):.2f}".replace(".", ",")
    except Exception:
        return "R$ 0,00"


def formatar_percentual(valor):
    try:
        return f"{float(valor):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def calcular_indicadores_produto(df_produto):
    df = df_produto.copy()

    df["valor_kg"] = pd.to_numeric(df["valor_kg"], errors="coerce").fillna(0)
    df = df[df["valor_kg"] > 0].copy()

    if df.empty:
        return None

    df = df.sort_values("data")

    preco_medio = df["valor_kg"].mean()
    preco_minimo = df["valor_kg"].min()
    preco_maximo = df["valor_kg"].max()
    registros = len(df)

    primeiro_preco = df.iloc[0]["valor_kg"]
    ultimo_preco = df.iloc[-1]["valor_kg"]

    if primeiro_preco > 0:
        variacao = ((ultimo_preco - primeiro_preco) / primeiro_preco) * 100
    else:
        variacao = 0

    amplitude = preco_maximo - preco_minimo

    return {
        "preco_medio": preco_medio,
        "preco_minimo": preco_minimo,
        "preco_maximo": preco_maximo,
        "variacao": variacao,
        "amplitude": amplitude,
        "registros": registros,
        "primeiro_preco": primeiro_preco,
        "ultimo_preco": ultimo_preco
    }

def baixar_imagem_url(url):
    if not url:
        return None

    try:
        resposta = requests.get(url, timeout=10)

        if resposta.status_code == 200:
            return Image.open(BytesIO(resposta.content))

        return None

    except Exception:
        return None


def gerar_insights_produto(produto_nome, indicadores):
    insights = []

    variacao = indicadores["variacao"]
    preco_medio = indicadores["preco_medio"]
    preco_minimo = indicadores["preco_minimo"]
    preco_maximo = indicadores["preco_maximo"]

    insights.append(
        f"O produto {produto_nome} apresentou preço médio de {formatar_moeda(preco_medio)} por kg no período analisado."
    )

    insights.append(
        f"O menor preço observado foi {formatar_moeda(preco_minimo)} por kg, enquanto o maior foi {formatar_moeda(preco_maximo)} por kg."
    )

    if variacao > 10:
        tendencia = "tendência de alta"
    elif variacao < -10:
        tendencia = "tendência de queda"
    else:
        tendencia = "comportamento relativamente estável"

    insights.append(
        f"No período selecionado, o produto apresentou {tendencia}, com variação de {formatar_percentual(variacao)}."
    )

    return insights

def quebrar_texto(texto, largura=50):
    if not texto:
        return "Não informado."
    return textwrap.fill(str(texto), width=largura)


def desenhar_card(ax, facecolor="#0B1A2B"):
    ax.set_facecolor(facecolor)
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)


def gerar_insights_produto_curto(produto_nome, indicadores):
    insights = []

    preco_medio = indicadores["preco_medio"]
    preco_minimo = indicadores["preco_minimo"]
    preco_maximo = indicadores["preco_maximo"]
    variacao = indicadores["variacao"]

    insights.append(
        f"{produto_nome} apresentou preço médio de {formatar_moeda(preco_medio)} por kg no período."
    )

    insights.append(
        f"O menor preço foi {formatar_moeda(preco_minimo)} e o maior foi {formatar_moeda(preco_maximo)}."
    )

    if variacao > 10:
        insights.append(
            f"O produto apresentou tendência de alta, com variação de {formatar_percentual(variacao)}."
        )
    elif variacao < -10:
        insights.append(
            f"O produto apresentou tendência de queda, com variação de {formatar_percentual(variacao)}."
        )
    else:
        insights.append(
            f"O produto apresentou comportamento relativamente estável, com variação de {formatar_percentual(variacao)}."
        )

    return insights

def formatar_bullets(lista, largura=100):
    itens = []

    for item in lista:
        texto = textwrap.fill(
            item,
            width=largura,
            initial_indent="• ",
            subsequent_indent="  "
        )
        itens.append(texto)

    return "\n\n".join(itens)

def gerar_post_produto_png(
    produto_nome,
    produto_classe,
    produto_unidade,
    data_inicial,
    data_final,
    info_produto,
    indicadores,
    df_periodo
):
    fig = plt.figure(figsize=(10.8, 13.8))
    fig.patch.set_facecolor("#030B17")

    gs = fig.add_gridspec(
        nrows=30,
        ncols=12,
        left=0.05,
        right=0.95,
        top=0.97,
        bottom=0.04,
        hspace=1.0,
        wspace=0.65
    )

    # ================= CABEÇALHO =================
    ax_header = fig.add_subplot(gs[0:2, :])
    ax_header.axis("off")

    logo_path = "logo.png"

    if os.path.exists(logo_path):
        logo_img = Image.open(logo_path)

        ax_logo = fig.add_axes([0.06, 0.915, 0.08, 0.08])
        ax_logo.imshow(logo_img)
        ax_logo.axis("off")

    ax_header.text(
        0.5, 0.86,
        "AMA - AUTARQUIA MUNICIPAL DE ABASTECIMENTO",
        fontsize=18,
        fontweight="bold",
        color="#8EC5FF",
        ha="center",
        va="center",
        transform=ax_header.transAxes
    )

    ax_header.text(
        0.5, 0.10,
        "Ficha Analítica do Produto",
        fontsize=38,
        fontweight="bold",
        color="white",
        ha="center",
        va="center",
        transform=ax_header.transAxes
    )

    # ================= SUBCABEÇALHO =================
    ax_sub = fig.add_subplot(gs[2:3, :])
    ax_sub.axis("off")

    ax_sub.text(
        0.01, 0.5,
        f"Classe: {produto_classe}   |   Produto: {produto_nome}   |   Período: {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}",
        fontsize=11,
        color="#D1D9E6",
        style="italic",
        ha="left",
        va="center",
        transform=ax_sub.transAxes
    )

    # ================= FOTO =================
    ax_foto = fig.add_subplot(gs[3:9, 0:4])
    ax_foto.set_facecolor("none")
    ax_foto.set_xticks([])
    ax_foto.set_yticks([])

    for spine in ax_foto.spines.values():
        spine.set_visible(False)

    foto_url = info_produto.get("foto_url", "")
    imagem = baixar_imagem_url(foto_url)

    if imagem is not None:
        ax_foto.imshow(imagem)
    else:
        ax_foto.text(
            0.5, 0.5,
            "Sem foto",
            ha="center",
            va="center",
            color="white",
            fontsize=14,
            transform=ax_foto.transAxes
        )

    # ================= DESCRIÇÃO =================
    ax_desc = fig.add_subplot(gs[3:9, 4:12])
    desenhar_card(ax_desc)
    ax_desc.axis("off")

    descricao = info_produto.get("descricao_curta", "") or "Sem descrição cadastrada."

    ax_desc.text(
        0.04, 0.84,
        produto_nome,
        fontsize=22,
        fontweight="bold",
        color="white",
        transform=ax_desc.transAxes
    )

    ax_desc.text(
        0.04, 0.68,
        f"Classe: {produto_classe}",
        fontsize=11.5,
        color="#D1D9E6",
        transform=ax_desc.transAxes
    )

    ax_desc.text(
        0.04, 0.58,
        f"Unidade: {produto_unidade}",
        fontsize=11.5,
        color="#D1D9E6",
        transform=ax_desc.transAxes
    )

    ax_desc.text(
        0.04, 0.38,
        "Descrição",
        fontsize=13,
        fontweight="bold",
        color="#88BFF0",
        transform=ax_desc.transAxes
    )

    ax_desc.text(
        0.04, 0.08,
        quebrar_texto(descricao, 68),
        fontsize=11.5,
        color="white",
        va="bottom",
        transform=ax_desc.transAxes
    )

    # ================= KPIs =================
    kpi_titulos = ["Preço médio/kg", "Menor preço/kg", "Maior preço/kg", "Variação"]
    kpi_valores = [
        formatar_moeda(indicadores["preco_medio"]),
        formatar_moeda(indicadores["preco_minimo"]),
        formatar_moeda(indicadores["preco_maximo"]),
        formatar_percentual(indicadores["variacao"])
    ]

    kpi_axes = [
        fig.add_subplot(gs[9:11, 0:3]),
        fig.add_subplot(gs[9:11, 3:6]),
        fig.add_subplot(gs[9:11, 6:9]),
        fig.add_subplot(gs[9:11, 9:12]),
    ]

    for i, ax in enumerate(kpi_axes):
        ax.set_facecolor("none")
        ax.set_xticks([])
        ax.set_yticks([])

        for spine in ax.spines.values():
            spine.set_visible(False)

        if kpi_titulos[i] == "Preço médio/kg":
            cor_valor = "#4FA3FF"   # azul
        elif kpi_titulos[i] == "Menor preço/kg":
            cor_valor = "#34D399"   # verde
        elif kpi_titulos[i] == "Maior preço/kg":
            cor_valor = "#F59E0B"   # laranja
        elif kpi_titulos[i] == "Variação":
            if indicadores["variacao"] > 0:
                cor_valor = "#4FA3FF"
            elif indicadores["variacao"] < 0:
                cor_valor = "#FF8A65"
            else:
                cor_valor = "white"
        else:
            cor_valor = "white"

        ax.text(
            0.08, 0.68,
            kpi_titulos[i],
            fontsize=10.5,
            color="#9FB3C8",
            fontweight="bold",
            transform=ax.transAxes
        )

        ax.text(
            0.08, 0.28,
            kpi_valores[i],
            fontsize=18,
            color=cor_valor,
            fontweight="bold",
            transform=ax.transAxes
        )

    # ================= GRÁFICO PRINCIPAL =================
    ax_graf = fig.add_subplot(gs[12:17, :])
    ax_graf.set_facecolor("#0B1A2B")

    for spine in ax_graf.spines.values():
        spine.set_visible(False)

    df_grafico = (
        df_periodo
        .groupby("data", as_index=False)
        .agg(valor_kg=("valor_kg", "mean"))
        .sort_values("data")
    )

    marcador, estilo_linha = obter_estilo_linha(0)

    ax_graf.plot(
        df_grafico["data"],
        df_grafico["valor_kg"],
        color="white",
        linestyle=estilo_linha,
        marker=marcador,
        linewidth=2.4,
        markersize=5.5,
        markerfacecolor="#0B1A2B",
        markeredgecolor="white",
        markeredgewidth=1.2,
        label="Preço por kg"
    )

    media_periodo = df_grafico["valor_kg"].mean()
    ax_graf.axhline(
        media_periodo,
        color="#BFC7D5",
        linestyle="--",
        linewidth=1.4,
        alpha=0.95,
        label="Média do período"
    )

    ax_graf.set_title(
        "Comportamento dos preços no período",
        fontsize=16,
        fontweight="bold",
        color="white",
        pad=12
    )

    ax_graf.grid(True, alpha=0.10, color="white")
    ax_graf.set_axisbelow(True)

    ax_graf.tick_params(axis="x", colors="white", rotation=30, labelsize=9)
    ax_graf.tick_params(axis="y", colors="white", labelsize=9)

    ax_graf.set_ylabel("Preço por Kg (R$)", color="white", fontsize=10.5)
    ax_graf.set_xlabel("")

    ax_graf.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax_graf.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

    ax_graf.legend(
        loc="best",
        fontsize=8.5,
        frameon=True,
        facecolor="#0B1A2B",
        edgecolor="white",
        labelcolor="white"
    )

    # ================= NUTRIÇÃO =================
    ax_nutri = fig.add_subplot(gs[18:22, 0:6])
    desenhar_card(ax_nutri)
    ax_nutri.axis("off")

    vitaminas = info_produto.get("vitaminas", "") or "Não informado."
    minerais = info_produto.get("minerais", "") or "Não informado."
    beneficios = info_produto.get("beneficios", "") or "Não informado."

    ax_nutri.text(
        0.03, 0.84,
        "Informações nutricionais",
        fontsize=15,
        fontweight="bold",
        color="white",
        transform=ax_nutri.transAxes
    )

    texto_nutri = (
        f"Vitaminas: {vitaminas}\n\n"
        f"Minerais: {minerais}\n\n"
        f"Benefícios: {beneficios}"
    )

    ax_nutri.text(
        0.03, 0.66,
        quebrar_texto(texto_nutri, 48),
        fontsize=11.5,
        color="#E2E8F0",
        va="top",
        transform=ax_nutri.transAxes
    )

    # ================= MERCADO =================
    ax_mercado = fig.add_subplot(gs[18:22, 6:12])
    desenhar_card(ax_mercado)
    ax_mercado.axis("off")

    comportamento = info_produto.get("comportamento_ceasa", "") or "Não informado."
    sazonalidade = info_produto.get("sazonalidade", "") or "Não informado."

    ax_mercado.text(
        0.03, 0.84,
        "Mercado",
        fontsize=15,
        fontweight="bold",
        color="white",
        transform=ax_mercado.transAxes
    )

    texto_mercado = (
        f"Comportamento no Ceasa: {comportamento}\n\n"
        f"Sazonalidade: {sazonalidade}"
    )

    ax_mercado.text(
        0.03, 0.66,
        quebrar_texto(texto_mercado, 58),
        fontsize=9.4,
        color="#E2E8F0",
        va="top",
        transform=ax_mercado.transAxes
    )

    # ================= PRINCIPAIS INSIGHTS =================
    ax_insights = fig.add_subplot(gs[24:29, :])
    desenhar_card(ax_insights)
    ax_insights.axis("off")

    insights = gerar_insights_produto_curto(produto_nome, indicadores)

    ax_insights.text(
        0.5, 0.82,
        "Principais insights",
        fontsize=16,
        fontweight="bold",
        color="white",
        ha="center",
        transform=ax_insights.transAxes
    )

    texto_insights = formatar_bullets(insights, largura=105)

    ax_insights.text(
        0.05, 0.62,
        texto_insights,
        fontsize=11,
        color="#E2E8F0",
        va="top",
        transform=ax_insights.transAxes
    )

    # ================= RODAPÉ =================
    ax_footer = fig.add_subplot(gs[29:30, :])
    ax_footer.axis("off")

    ax_footer.text(
        0.5, 0.4,
        f"AMA | Sistema de Cotação | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        fontsize=9,
        color="#94A3B8",
        ha="center",
        transform=ax_footer.transAxes
    )

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    caminho = temp.name
    temp.close()

    fig.savefig(
        caminho,
        dpi=220,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight"
    )
    plt.close(fig)

    return caminho

def tela_post_produto_unitario(supabase):
    st.title("🥑 Post Unitário do Produto")

    st.info(
        "Nesta tela vamos gerar uma análise individual de um produto, "
        "com informações nutricionais, comportamento no Ceasa e evolução dos preços."
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

        descricao = info_produto.get("descricao_curta", "")

        if descricao:
            st.write(descricao)
        else:
            st.warning("Produto sem descrição cadastrada.")

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

    figura_grafico, eixo_grafico = plt.subplots(
        figsize=(10, 4.5)
    )

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

    eixo_grafico.set_title(
        f"Comportamento dos preços - {produto_nome}"
    )
    eixo_grafico.set_xlabel("Data")
    eixo_grafico.set_ylabel("Preço por kg (R$)")

    aplicar_estilo_impressao(eixo_grafico)

    eixo_grafico.legend(
        loc="best",
        frameon=True,
        edgecolor="black"
    )

    eixo_grafico.xaxis.set_major_locator(
        mdates.AutoDateLocator()
    )
    eixo_grafico.xaxis.set_major_formatter(
        mdates.DateFormatter("%d/%m")
    )

    figura_grafico.autofmt_xdate()
    figura_grafico.tight_layout()

    st.pyplot(figura_grafico)
    plt.close(figura_grafico)

    st.markdown("---")

    st.subheader("🥗 Informações nutricionais e de mercado")

    col_nutri, col_ceasa = st.columns(2)

    with col_nutri:
        st.markdown("#### Nutrição")

        st.write("**Vitaminas:**")
        st.write(info_produto.get("vitaminas", "") or "Não informado.")

        st.write("**Minerais:**")
        st.write(info_produto.get("minerais", "") or "Não informado.")

        st.write("**Benefícios:**")
        st.write(info_produto.get("beneficios", "") or "Não informado.")

    with col_ceasa:
        st.markdown("#### Comportamento no Ceasa")

        st.write(info_produto.get("comportamento_ceasa", "") or "Não informado.")

        st.write("**Sazonalidade:**")
        st.write(info_produto.get("sazonalidade", "") or "Não informado.")

    st.markdown("---")

    if st.button("🖼️ Gerar post do produto", type="primary"):
        try:
            caminho_post = gerar_post_produto_png(
                produto_nome=produto_nome,
                produto_classe=produto_classe,
                produto_unidade=produto_unidade,
                data_inicial=data_inicial,
                data_final=data_final,
                info_produto=info_produto,
                indicadores=indicadores,
                df_periodo=df_periodo
            )

            st.success("Post gerado com sucesso.")
            st.image(caminho_post, caption="Prévia do post", use_container_width=True)

            with open(caminho_post, "rb") as arq:
                st.download_button(
                    "⬇️ Baixar post em PNG",
                    data=arq,
                    file_name=f"post_{produto_nome.lower()}.png",
                    mime="image/png"
                )

        except Exception as e:
            st.error(f"Erro ao gerar o post: {e}")