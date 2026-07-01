import os
import textwrap
import tempfile

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from datetime import datetime
from matplotlib.patches import FancyBboxPatch, Circle, Arc
from matplotlib.lines import Line2D

from dados_utils import carregar_todas_cotacoes
from utils import corrigir_classe
from graficos_utils import (
    obter_estilo_linha,
    aplicar_estilo_impressao
)


# ===================== FORMATAÇÕES =====================
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


def formatar_percentual_curto(valor):
    try:
        return f"{float(valor):.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"


def limitar_texto(texto, limite=24):
    texto = str(texto).strip()

    if len(texto) <= limite:
        return texto

    return texto[:limite - 3] + "..."


def quebrar_rotulo_produto(texto, limite_total=30, largura_linha=18):
    """Organiza nomes longos dos produtos nos gráficos de barras.

    A ideia é manter nomes curtos em uma linha e quebrar apenas quando
    realmente precisar, evitando rótulos desalinhados ou apertados.
    """
    texto = str(texto).strip().upper()
    texto = " ".join(texto.split())
    texto = limitar_texto(texto, limite_total)

    # Se tiver complemento entre parênteses, deixa o complemento em uma linha própria.
    # Ex.: AMEIXA FRESCA (IMP.) -> AMEIXA FRESCA / (IMP.)
    if "(" in texto and ")" in texto and len(texto) > largura_linha:
        antes = texto.split("(")[0].strip()
        depois = "(" + texto.split("(", 1)[1].strip()

        if len(antes) <= largura_linha + 4:
            return f"{antes}\n{depois}"

    return textwrap.fill(
        texto,
        width=largura_linha,
        break_long_words=False,
        break_on_hyphens=False
    )


# ===================== CORES DO LAYOUT =====================
AZUL_ESCURO = "#082B75"
AZUL = "#0057D9"
AZUL_CLARO = "#EAF2FF"
VERMELHO = "#D71920"
VERMELHO_CLARO = "#FFF0F0"
CINZA_TEXTO = "#1D2635"
CINZA_SUAVE = "#D8DEE8"
FUNDO = "#FFFFFF"


# ===================== FUNÇÕES VISUAIS =====================
def add_card(fig, x, y, w, h, radius=0.018, facecolor="#FFFFFF", edgecolor="#DDE4EF", shadow=True, lw=1.0):
    """Adiciona um card arredondado em coordenadas da figura."""
    if shadow:
        sombra = FancyBboxPatch(
            (x + 0.004, y - 0.004),
            w,
            h,
            boxstyle=f"round,pad=0.006,rounding_size={radius}",
            transform=fig.transFigure,
            facecolor="#000000",
            edgecolor="none",
            alpha=0.08,
            zorder=0
        )
        fig.patches.append(sombra)

    card = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.006,rounding_size={radius}",
        transform=fig.transFigure,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        zorder=1
    )
    fig.patches.append(card)

    return card


def add_decoracoes_fundo(fig):
    """Cria fundo institucional claro, mais suave e sem competir com os gráficos."""
    ax_bg = fig.add_axes([0, 0, 1, 1], zorder=-10)
    ax_bg.set_xlim(0, 1)
    ax_bg.set_ylim(0, 1)
    ax_bg.axis("off")
    ax_bg.set_facecolor(FUNDO)

    # Manchas suaves, bem discretas
    for x, y, r, cor, alpha in [
        (0.01, 0.18, 0.13, "#F4C15D", 0.055),
        (0.01, 0.45, 0.14, "#6ABF69", 0.040),
        (0.98, 0.34, 0.14, "#E0B05B", 0.045),
        (0.98, 0.17, 0.12, "#D4A24D", 0.055),
        (0.04, 0.83, 0.10, "#8FCB88", 0.035),
    ]:
        ax_bg.add_patch(Circle((x, y), r, facecolor=cor, edgecolor="none", alpha=alpha))

    # Faixas curvas superiores à esquerda, um pouco menores
    for cor, lw, desloc in [(VERMELHO, 14, 0.000), (AZUL, 8, 0.018), ("#FFFFFF", 4, 0.030)]:
        ax_bg.add_patch(
            Arc(
                (-0.055, 1.055 - desloc),
                0.40,
                0.24,
                angle=0,
                theta1=205,
                theta2=360,
                color=cor,
                linewidth=lw,
                alpha=0.96,
                capstyle="round"
            )
        )

    # Faixas curvas inferiores à direita, mais delicadas
    for cor, lw, desloc in [(AZUL, 18, 0.000), ("#006DFF", 9, 0.018), (VERMELHO, 5, 0.039), ("#FFFFFF", 3, 0.052)]:
        ax_bg.add_patch(
            Arc(
                (1.04, -0.035 + desloc),
                0.46,
                0.30,
                angle=0,
                theta1=20,
                theta2=190,
                color=cor,
                linewidth=lw,
                alpha=0.96,
                capstyle="round"
            )
        )

    # Pontos decorativos no canto superior direito, bem suaves
    xs = [0.845 + i * 0.024 for i in range(7)]
    ys = [0.928 + j * 0.021 for j in range(5)]
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            ax_bg.plot(
                x,
                y,
                "o",
                color=AZUL,
                alpha=0.065 + 0.012 * ((i + j) % 2),
                markersize=2.3
            )

    return ax_bg

def criar_card_kpi(fig, pos, titulo, valor, produto, cor=AZUL, icone="↑"):
    """Card superior com indicador principal, ícone redondo e layout mais elegante."""
    x, y, w, h = pos
    add_card(fig, x, y, w, h, radius=0.017, facecolor="#FFFFFF", edgecolor="#D9E2F0", shadow=True)

    ax = fig.add_axes([x, y, w, h], zorder=3)
    ax.axis("off")

    # Ícone realmente circular usando scatter, para não virar oval em eixos retangulares
    ax.scatter(
        [0.16],
        [0.51],
        s=1850,
        color=cor,
        transform=ax.transAxes,
        clip_on=False,
        zorder=3
    )
    ax.text(
        0.16,
        0.51,
        icone,
        ha="center",
        va="center",
        fontsize=21 if icone != "R$" else 18,
        color="white",
        fontweight="bold",
        transform=ax.transAxes,
        zorder=4
    )

    ax.text(0.32, 0.72, titulo, fontsize=12.4, color=cor, fontweight="bold", transform=ax.transAxes)
    ax.text(0.32, 0.42, valor, fontsize=24, color=cor, fontweight="bold", transform=ax.transAxes)
    ax.text(0.32, 0.19, limitar_texto(produto, 27), fontsize=9.0, color=CINZA_TEXTO, fontweight="bold", transform=ax.transAxes)

    ax.add_line(Line2D([0.025, 0.975], [0.025, 0.025], transform=ax.transAxes, color=cor, linewidth=2.7, solid_capstyle="round"))

    return ax

def criar_titulo_card(ax, titulo):
    ax.set_title(titulo, fontsize=13.5, color=AZUL_ESCURO, fontweight="bold", pad=12)


def plotar_ranking_barras(ax, df_plot, titulo, tipo="alta"):
    ax.set_facecolor("#FFFFFF")

    if df_plot is None or df_plot.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Sem dados",
            ha="center",
            va="center",
            color=CINZA_TEXTO,
            fontsize=12,
            transform=ax.transAxes
        )
        return

    df_plot = df_plot.copy()
    df_plot["produto_curto"] = df_plot["produto"].apply(
        lambda x: quebrar_rotulo_produto(x, limite_total=30, largura_linha=18)
    )

    if tipo == "alta":
        df_plot = df_plot.sort_values("variacao_percentual", ascending=True)
        cor_barra = AZUL
        x_min = 0
        x_max = max(float(df_plot["variacao_percentual"].max()), 5) * 1.20
    else:
        df_plot = df_plot.sort_values("variacao_percentual", ascending=False)
        cor_barra = VERMELHO
        x_min = min(float(df_plot["variacao_percentual"].min()), -5) * 1.26
        x_max = 0

    valores = df_plot["variacao_percentual"].astype(float).reset_index(drop=True)
    rotulos = df_plot["produto_curto"].tolist()
    posicoes = list(range(len(df_plot)))

    barras = ax.barh(
        posicoes,
        valores,
        color=cor_barra,
        edgecolor="black",
        linewidth=0.9,
        alpha=0.92,
        height=0.46
    )

    # Remove o rótulo padrão do eixo Y e desenha os nomes manualmente,
    # como uma coluna organizada dentro do card.
    ax.set_yticks(posicoes)
    ax.set_yticklabels([])
    ax.tick_params(axis="y", length=0)

    transformacao_rotulo = ax.get_yaxis_transform()

    for y, rotulo in zip(posicoes, rotulos):
        ax.text(
            -0.02,
            y,
            rotulo,
            ha="right",
            va="center",
            fontsize=7.9,
            color=CINZA_TEXTO,
            linespacing=0.88,
            rotation=12,
            rotation_mode="anchor",
            transform=transformacao_rotulo,
            clip_on=False
        )

    criar_titulo_card(ax, titulo)

    aplicar_estilo_impressao(ax)
    ax.grid(False)

    ax.tick_params(axis="x", colors=CINZA_TEXTO, labelsize=8.2)
    ax.set_xlabel("Variação (%)", color=CINZA_TEXTO, fontsize=8.6)
    ax.set_ylabel("")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-0.65, len(df_plot) - 0.35)

    if tipo == "alta":
        referencia = max(x_max, 1)
        for i, v in enumerate(valores):
            ax.text(
                v + referencia * 0.025,
                i,
                formatar_percentual_curto(v),
                va="center",
                ha="left",
                color=CINZA_TEXTO,
                fontsize=8.0,
                fontweight="bold"
            )
    else:
        referencia = max(abs(x_min), 1)
        for i, v in enumerate(valores):
            ax.text(
                v - referencia * 0.035,
                i,
                formatar_percentual_curto(v),
                va="center",
                ha="right",
                color=CINZA_TEXTO,
                fontsize=8.0,
                fontweight="bold"
            )

def plotar_grafico_historico(ax, historico_3):
    ax.set_facecolor("#FFFFFF")

    if historico_3 is None or historico_3.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Sem histórico disponível",
            ha="center",
            va="center",
            color=CINZA_TEXTO,
            fontsize=12,
            transform=ax.transAxes
        )
        return

    cores = [AZUL, "#FF7A00", "#2EAF4A", VERMELHO, "#6F42C1"]

    datas_validas = pd.to_datetime(
        historico_3["data"],
        errors="coerce"
    ).dropna()

    data_min = datas_validas.min() if not datas_validas.empty else None
    data_max = datas_validas.max() if not datas_validas.empty else None

    for idx, produto in enumerate(
        historico_3["produto"].dropna().unique()
    ):
        df_prod = historico_3[
            historico_3["produto"] == produto
        ].copy()
        df_prod = df_prod.sort_values("data")

        marcador, estilo_linha = obter_estilo_linha(idx)

        ax.plot(
            df_prod["data"],
            df_prod["valor_kg"],
            linewidth=2.2,
            linestyle=estilo_linha,
            marker=marcador,
            markersize=5.4,
            color=cores[idx % len(cores)],
            markerfacecolor="white",
            markeredgecolor="black",
            markeredgewidth=0.9,
            label=limitar_texto(produto, 28)
        )

    ax.set_title(
        "Evolução do preço por kg — 3 produtos com maior variação",
        fontsize=14,
        color=AZUL_ESCURO,
        fontweight="bold",
        pad=12
    )

    aplicar_estilo_impressao(ax)
    ax.grid(True, alpha=0.28, color="#A9B6C8", linestyle=":", linewidth=0.65)
    ax.set_axisbelow(True)

    ax.tick_params(axis="x", colors=CINZA_TEXTO, rotation=35, labelsize=8.2)
    ax.tick_params(axis="y", colors=CINZA_TEXTO, labelsize=8.2)
    ax.set_ylabel("Preço por Kg (R$)", color=CINZA_TEXTO, fontsize=9.2)
    ax.set_xlabel("")

    # Evita repetição excessiva de datas no eixo X
    if data_min is not None and data_max is not None:
        dias = max(1, (data_max.date() - data_min.date()).days)
        intervalo = max(1, int(round(dias / 4)))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=intervalo))
    else:
        ax.xaxis.set_major_locator(
            mdates.AutoDateLocator(minticks=3, maxticks=5)
        )

    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%d/%m")
    )

    ax.legend(
        fontsize=7.8,
        loc="upper left",
        frameon=True,
        edgecolor="black",
        facecolor="white",
        labelcolor=CINZA_TEXTO
    )


# ===================== INSIGHTS =====================
def gerar_insights_post(top_maiores, top_menores, top_variacao, ranking_quedas):
    insights = []

    if top_variacao is not None and not top_variacao.empty:
        produto = top_variacao.iloc[0]["produto"]
        variacao = top_variacao.iloc[0]["variacao_percentual"]
        insights.append(
            f"{produto} apresentou a maior variação do período, com oscilação de {formatar_percentual(variacao)}."
        )

    if top_maiores is not None and not top_maiores.empty:
        produto = top_maiores.iloc[0]["produto"]
        valor = top_maiores.iloc[0]["valor_kg"]
        insights.append(
            f"{produto} registrou o maior preço por kg no período, atingindo {formatar_moeda(valor)}."
        )

    if top_menores is not None and not top_menores.empty:
        produto = top_menores.iloc[0]["produto"]
        valor = top_menores.iloc[0]["valor_kg"]
        insights.append(
            f"{produto} apresentou o menor preço por kg, com valor de {formatar_moeda(valor)}."
        )

    if ranking_quedas is not None and not ranking_quedas.empty:
        produto = ranking_quedas.iloc[0]["produto"]
        valor = ranking_quedas.iloc[0]["variacao_percentual"]
        insights.append(
            f"A maior queda observada foi de {produto}, com variação de {formatar_percentual(valor)}."
        )

    insights.append(
        "As movimentações sugerem influência de oferta, sazonalidade, custos de produção e logística no período analisado."
    )

    return insights[:5]


# ===================== PREPARAÇÃO DOS DADOS =====================
def preparar_dados_post(df_periodo):
    df = df_periodo.copy()

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    colunas_numericas = [
        "kg",
        "preco_min",
        "preco_max",
        "preco_medio",
        "valor_kg"
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[df["preco_medio"] > 0].copy()

    if df.empty:
        return None

    resumo_produtos = (
        df.groupby(["produto", "classe"], as_index=False)
        .agg(
            preco_medio=("preco_medio", "mean"),
            valor_kg=("valor_kg", "mean"),
            qtd_registros=("valor_kg", "count")
        )
        .sort_values("valor_kg", ascending=False)
    )

    top_maiores = resumo_produtos.sort_values("valor_kg", ascending=False).head(5)
    top_menores = resumo_produtos.sort_values("valor_kg", ascending=True).head(5)

    df_ord = df.sort_values(["produto", "data"])

    primeira = df_ord.groupby("produto").first().reset_index()
    ultima = df_ord.groupby("produto").last().reset_index()

    comparativo = primeira[
        ["produto", "classe", "valor_kg", "data"]
    ].merge(
        ultima[
            ["produto", "valor_kg", "data"]
        ],
        on="produto",
        suffixes=("_inicial", "_final")
    )

    comparativo["diferenca"] = (
        comparativo["valor_kg_final"] -
        comparativo["valor_kg_inicial"]
    )

    comparativo["variacao_percentual"] = comparativo.apply(
        lambda row: (
            ((row["valor_kg_final"] - row["valor_kg_inicial"]) / row["valor_kg_inicial"]) * 100
            if row["valor_kg_inicial"] > 0 else 0
        ),
        axis=1
    )

    comparativo["variacao_absoluta"] = comparativo["variacao_percentual"].abs()

    ranking_altas = comparativo[
        comparativo["variacao_percentual"] > 0
    ].sort_values(
        "variacao_percentual",
        ascending=False
    ).head(5).copy()

    ranking_altas["valor_plot"] = ranking_altas["variacao_percentual"]

    ranking_quedas = comparativo[
        comparativo["variacao_percentual"] < 0
    ].sort_values(
        "variacao_percentual",
        ascending=True
    ).head(5).copy()

    ranking_quedas["valor_plot"] = ranking_quedas["variacao_percentual"]

    top_variacao = comparativo.sort_values(
        "variacao_absoluta",
        ascending=False
    ).head(3)

    produtos_variacao = top_variacao["produto"].tolist()

    historico_3 = df[df["produto"].isin(produtos_variacao)].copy()
    historico_3 = historico_3.sort_values(["produto", "data"])

    return {
        "top_maiores": top_maiores,
        "top_menores": top_menores,
        "top_variacao": top_variacao,
        "historico_3": historico_3,
        "ranking_altas": ranking_altas,
        "ranking_quedas": ranking_quedas
    }


# ===================== GERAÇÃO DO PNG =====================
def gerar_post_png(
    top_maiores,
    top_menores,
    top_variacao,
    historico_3,
    ranking_altas,
    ranking_quedas,
    data_inicial,
    data_final,
    classe_sel,
    logo_path=None
):
    insights = gerar_insights_post(
        top_maiores,
        top_menores,
        top_variacao,
        ranking_quedas
    )

    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(FUNDO)

    add_decoracoes_fundo(fig)

    # =========================================================
    # CABEÇALHO
    # =========================================================
    ax_header = fig.add_axes([0.06, 0.842, 0.88, 0.125], zorder=5)
    ax_header.axis("off")

    if logo_path and os.path.exists(logo_path):
        try:
            img = plt.imread(logo_path)
            ax_logo = fig.add_axes([0.095, 0.862, 0.225, 0.080], zorder=7)
            ax_logo.imshow(img)
            ax_logo.axis("off")
        except Exception:
            ax_header.text(
                0.02, 0.48,
                "AMA",
                fontsize=48,
                color=AZUL_ESCURO,
                fontweight="bold",
                transform=ax_header.transAxes
            )
    else:
        ax_header.text(
            0.02, 0.48,
            "AMA",
            fontsize=48,
            color=AZUL_ESCURO,
            fontweight="bold",
            transform=ax_header.transAxes
        )

    ax_header.text(
        0.385, 0.76,
        "MERCADO DO PRODUTOR DE JUAZEIRO-BA",
        fontsize=12.5,
        fontweight="bold",
        color=AZUL,
        ha="left",
        transform=ax_header.transAxes
    )

    ax_header.text(
        0.385, 0.39,
        "Análise de Preços",
        fontsize=36,
        fontweight="bold",
        color=AZUL_ESCURO,
        ha="left",
        transform=ax_header.transAxes
    )

    periodo_txt = f"Período: {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
    classe_txt = f"Classe: {classe_sel}"

    ax_header.text(
        0.385, 0.10,
        f"▣  {periodo_txt}    |    ◈  {classe_txt}",
        fontsize=10.5,
        color=CINZA_TEXTO,
        ha="left",
        transform=ax_header.transAxes
    )

    # =========================================================
    # CARDS DE INDICADORES
    # =========================================================
    if ranking_altas is not None and not ranking_altas.empty:
        criar_card_kpi(
            fig,
            [0.07, 0.735, 0.27, 0.085],
            "Maior alta",
            formatar_percentual(ranking_altas.iloc[0]["variacao_percentual"]),
            ranking_altas.iloc[0]["produto"],
            cor=AZUL,
            icone="↗"
        )
    else:
        criar_card_kpi(fig, [0.07, 0.735, 0.27, 0.085], "Maior alta", "0,00%", "Sem dados", cor=AZUL, icone="↗")

    if ranking_quedas is not None and not ranking_quedas.empty:
        criar_card_kpi(
            fig,
            [0.365, 0.735, 0.27, 0.085],
            "Maior queda",
            formatar_percentual(ranking_quedas.iloc[0]["variacao_percentual"]),
            ranking_quedas.iloc[0]["produto"],
            cor=VERMELHO,
            icone="↘"
        )
    else:
        criar_card_kpi(fig, [0.365, 0.735, 0.27, 0.085], "Maior queda", "0,00%", "Sem dados", cor=VERMELHO, icone="↘")

    if top_maiores is not None and not top_maiores.empty:
        criar_card_kpi(
            fig,
            [0.66, 0.735, 0.27, 0.085],
            "Maior preço/kg",
            formatar_moeda(top_maiores.iloc[0]["valor_kg"]),
            top_maiores.iloc[0]["produto"],
            cor=AZUL_ESCURO,
            icone="R$"
        )
    else:
        criar_card_kpi(fig, [0.66, 0.735, 0.27, 0.085], "Maior preço/kg", "R$ 0,00", "Sem dados", cor=AZUL_ESCURO, icone="R$")

    # =========================================================
    # RANKINGS DE BARRAS
    # =========================================================
    add_card(fig, 0.065, 0.505, 0.415, 0.195, radius=0.018, facecolor="#FFFFFF", edgecolor="#DCE4EF", shadow=True)
    ax_altas = fig.add_axes([0.160, 0.535, 0.275, 0.13], zorder=5)
    plotar_ranking_barras(ax_altas, ranking_altas, "Top 5 maiores altas", tipo="alta")

    add_card(fig, 0.515, 0.505, 0.415, 0.195, radius=0.018, facecolor="#FFFFFF", edgecolor="#DCE4EF", shadow=True)
    ax_quedas = fig.add_axes([0.640, 0.535, 0.240, 0.13], zorder=5)
    plotar_ranking_barras(ax_quedas, ranking_quedas, "Top 5 maiores quedas", tipo="queda")

    # =========================================================
    # GRÁFICO DE EVOLUÇÃO
    # =========================================================
    add_card(fig, 0.065, 0.265, 0.865, 0.205, radius=0.018, facecolor="#FFFFFF", edgecolor="#DCE4EF", shadow=True)
    ax_hist = fig.add_axes([0.115, 0.295, 0.765, 0.14], zorder=5)
    plotar_grafico_historico(ax_hist, historico_3)

    # =========================================================
    # INSIGHTS
    # =========================================================
    add_card(fig, 0.07, 0.075, 0.86, 0.155, radius=0.018, facecolor="#FFFFFF", edgecolor="none", shadow=False)
    ax_insights = fig.add_axes([0.07, 0.075, 0.86, 0.155], zorder=5)
    ax_insights.axis("off")

    ax_insights.text(
        0.07,
        0.83,
        "Principais insights",
        fontsize=21,
        fontweight="bold",
        color=AZUL_ESCURO,
        ha="left",
        transform=ax_insights.transAxes
    )
    ax_insights.add_line(Line2D([0.07, 0.19], [0.77, 0.77], transform=ax_insights.transAxes, color=VERMELHO, linewidth=2.6, solid_capstyle="round"))

    posicoes_y = [0.62, 0.47, 0.32, 0.17, 0.02]

    for linha, y in zip(insights, posicoes_y):
        linha_formatada = textwrap.fill(linha, width=125, break_long_words=False)
        ax_insights.text(
            0.09,
            y,
            "●",
            fontsize=10.5,
            color=AZUL,
            va="top",
            transform=ax_insights.transAxes
        )
        ax_insights.text(
            0.12,
            y,
            linha_formatada,
            fontsize=9.2,
            color=CINZA_TEXTO,
            va="top",
            transform=ax_insights.transAxes
        )

    # =========================================================
    # RODAPÉ
    # =========================================================
    ax_footer = fig.add_axes([0.06, 0.025, 0.88, 0.035], zorder=5)
    ax_footer.axis("off")
    ax_footer.text(
        0.5,
        0.5,
        f"AMA | Sistema de Cotação | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        fontsize=9,
        color=AZUL_ESCURO,
        ha="center",
        va="center",
        fontweight="bold",
        transform=ax_footer.transAxes
    )

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    caminho = temp.name
    temp.close()

    fig.savefig(
        caminho,
        dpi=170,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
        pad_inches=0.04
    )
    plt.close(fig)

    return caminho


# ===================== TELA STREAMLIT =====================
def tela_posts_analiticos(supabase):
    st.title("🖼️ Posts Analíticos")

    st.info(
        "Nesta tela você pode gerar um post analítico em PNG com rankings de preços, "
        "comportamento dos produtos e texto interpretativo automático."
    )

    try:
        df = carregar_todas_cotacoes(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        return

    if df.empty:
        st.warning("Ainda não há cotações cadastradas.")
        return

    df = df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    if df.empty:
        st.warning("Não há datas válidas nas cotações.")
        return

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

    for col in ["preco_min", "preco_max", "preco_medio", "valor_kg", "kg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[df["preco_medio"] > 0].copy()

    if df.empty:
        st.warning("Não há dados com preço maior que zero.")
        return

    st.subheader("🔎 Filtros")

    data_min = df["data"].min().date()
    data_max = df["data"].max().date()

    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicial = st.date_input(
            "Data inicial",
            value=data_min,
            min_value=data_min,
            max_value=data_max,
            key="post_data_inicial"
        )

    with col2:
        data_final = st.date_input(
            "Data final",
            value=data_max,
            min_value=data_min,
            max_value=data_max,
            key="post_data_final"
        )

    with col3:
        classe_sel = st.selectbox(
            "Classe",
            ["Todas"] + sorted(df["classe"].dropna().unique().tolist()),
            key="post_classe"
        )

    if data_inicial > data_final:
        st.warning("A data inicial não pode ser maior que a data final.")
        return

    df_periodo = df[
        (df["data"].dt.date >= data_inicial) &
        (df["data"].dt.date <= data_final)
    ].copy()

    if classe_sel != "Todas":
        df_periodo = df_periodo[df_periodo["classe"] == classe_sel].copy()

    if df_periodo.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        return

    st.caption(
        "O novo layout segue um padrão institucional claro, com cards, gráficos e insights automáticos."
    )

    if st.button("🖼️ Gerar post analítico em PNG", type="primary"):
        try:
            dados = preparar_dados_post(df_periodo)

            if dados is None:
                st.warning("Não foi possível gerar o post com os dados selecionados.")
                return

            logo_path = "logo_novo.png"

            caminho_png = gerar_post_png(
                top_maiores=dados["top_maiores"],
                top_menores=dados["top_menores"],
                top_variacao=dados["top_variacao"],
                historico_3=dados["historico_3"],
                ranking_altas=dados["ranking_altas"],
                ranking_quedas=dados["ranking_quedas"],
                data_inicial=data_inicial,
                data_final=data_final,
                classe_sel=classe_sel,
                logo_path=logo_path
            )

            st.success("Post gerado com sucesso.")
            st.image(caminho_png, caption="Prévia do post analítico", use_container_width=True)

            with open(caminho_png, "rb") as f:
                st.download_button(
                    "📥 Baixar post em PNG",
                    data=f,
                    file_name=f"post_analitico_{datetime.now().strftime('%d-%m-%Y')}.png",
                    mime="image/png"
                )

        except Exception as e:
            st.error(f"Erro ao gerar o post: {e}")
