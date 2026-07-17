import os
import re
import zipfile
import pandas as pd
import textwrap
import tempfile
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from io import BytesIO
from PIL import Image
from matplotlib.patches import FancyBboxPatch, Rectangle

from graficos_utils import obter_estilo_linha


# =========================================================
# FORMATAÇÕES
# =========================================================
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

def texto_mpl(texto):
    """
    Evita que o Matplotlib interprete R$ como texto matemático.
    """
    return str(texto).replace("$", r"\$")



def nome_arquivo_seguro(texto):
    texto = str(texto or "").strip().lower()
    texto = re.sub(r"[^a-z0-9áàâãéêíóôõúç]+", "_", texto)
    texto = texto.strip("_")
    return texto or "produto"


def limitar_texto(texto, limite=42):
    texto = str(texto or "").strip()

    if len(texto) <= limite:
        return texto

    return texto[:limite - 3] + "..."


def quebrar_texto(texto, largura=50):
    if not texto:
        return "Não informado."

    return textwrap.fill(
        str(texto),
        width=largura,
        break_long_words=False,
        break_on_hyphens=False
    )


def formatar_bullets(lista, largura=100):
    itens = []

    for item in lista:
        texto = textwrap.fill(
            str(item),
            width=largura,
            initial_indent="• ",
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False
        )
        itens.append(texto)

    return "\n\n".join(itens)


# =========================================================
# DADOS DO PRODUTO
# =========================================================
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
            imagem = Image.open(BytesIO(resposta.content)).convert("RGBA")
            return imagem

        return None

    except Exception:
        return None


def obter_campo(info_produto, campo):
    valor = info_produto.get(campo, "")

    if valor is None:
        return "Não informado."

    valor = str(valor).strip()

    if valor == "":
        return "Não informado."

    return valor


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


# =========================================================
# VISUAL PADRÃO DOS POSTS
# =========================================================
AZUL_ESCURO = "#153F6D"
AZUL_TEXTO = "#173F6E"
AZUL_DESTAQUE = "#2F6FA5"
VERMELHO = "#B33A3A"
CINZA_FUNDO = "#EEF2F5"
CINZA_BORDA = "#CAD3DC"
CINZA_TEXTO = "#4F5E6B"
CINZA_ESCURO = "#2F3A43"
BRANCO = "#FFFFFF"


def adicionar_cartao(fig, ax, facecolor=BRANCO, edgecolor=CINZA_BORDA, sombra=True):
    ax.set_facecolor("none")
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)

    bbox = ax.get_position()

    if sombra:
        sombra_patch = FancyBboxPatch(
            (bbox.x0 + 0.004, bbox.y0 - 0.004),
            bbox.width,
            bbox.height,
            boxstyle="round,pad=0.008,rounding_size=0.018",
            transform=fig.transFigure,
            linewidth=0,
            facecolor="#AAB7C3",
            alpha=0.25,
            zorder=-30
        )
        fig.add_artist(sombra_patch)

    cartao = FancyBboxPatch(
        (bbox.x0, bbox.y0),
        bbox.width,
        bbox.height,
        boxstyle="round,pad=0.008,rounding_size=0.018",
        transform=fig.transFigure,
        linewidth=1.1,
        edgecolor=edgecolor,
        facecolor=facecolor,
        zorder=-29
    )
    fig.add_artist(cartao)


def desenhar_cabecalho(fig, gs, produto_nome, linha2):
    fig.add_artist(
        Rectangle(
            (0, 0.84),
            1,
            0.16,
            transform=fig.transFigure,
            facecolor=AZUL_ESCURO,
            edgecolor="none",
            zorder=-40
        )
    )

    ax_header = fig.add_subplot(gs[0:4, :])
    ax_header.axis("off")

    logo_path = "logo.png"

    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path)

            ax_logo = fig.add_axes([0.07, 0.872, 0.16, 0.095])
            ax_logo.imshow(logo_img)
            ax_logo.axis("off")
        except Exception:
            pass

    ax_header.text(
        0.56,
        0.80,
        "MERCADO DO PRODUTOR DE JUAZEIRO-BA",
        fontsize=16,
        fontweight="bold",
        color="white",
        ha="center",
        transform=ax_header.transAxes
    )

    ax_header.text(
        0.56,
        0.38,
        limitar_texto(produto_nome, 28),
        fontsize=32,
        fontweight="bold",
        color="white",
        ha="center",
        transform=ax_header.transAxes
    )

    ax_header.text(
        0.56,
        0.06,
        linha2,
        fontsize=11.5,
        color="#D9E6F2",
        ha="center",
        transform=ax_header.transAxes
    )


def desenhar_titulo_secao(ax, titulo, x=0.04, y=0.86, tamanho=18):
    ax.text(
        x,
        y,
        titulo,
        fontsize=tamanho,
        fontweight="bold",
        color=AZUL_TEXTO,
        transform=ax.transAxes
    )

    largura_linha = min(0.22, 0.035 + (len(titulo) * 0.012))

    ax.add_line(
        plt.Line2D(
            [x, x + largura_linha],
            [y - 0.06, y - 0.06],
            transform=ax.transAxes,
            color=VERMELHO,
            linewidth=2.2
        )
    )


def preparar_linhas(texto, largura, font_max, font_min, max_linhas):
    texto = str(texto or "Não informado.").strip()

    if texto == "":
        texto = "Não informado."

    font_max = float(font_max)
    font_min = float(font_min)

    # Trabalha em décimos para aceitar fontes como 8.8, 9.5 etc.
    inicio = int(round(font_max * 10))
    fim = int(round(font_min * 10))

    for fonte_10 in range(inicio, fim - 1, -1):
        fonte = fonte_10 / 10

        largura_ajustada = max(
            18,
            int(largura * (font_max / fonte))
        )

        linhas = []

        for paragrafo in texto.split("\n"):
            paragrafo = paragrafo.strip()

            if paragrafo == "":
                linhas.append("")
            else:
                linhas.extend(
                    textwrap.wrap(
                        paragrafo,
                        width=largura_ajustada,
                        break_long_words=False,
                        break_on_hyphens=False
                    )
                )

        if len(linhas) <= max_linhas:
            return "\n".join(linhas), fonte

    # Último recurso para não passar por cima de outro card.
    largura_ajustada = max(
        18,
        int(largura * (font_max / font_min))
    )

    linhas = []

    for paragrafo in texto.split("\n"):
        paragrafo = paragrafo.strip()

        if paragrafo == "":
            linhas.append("")
        else:
            linhas.extend(
                textwrap.wrap(
                    paragrafo,
                    width=largura_ajustada,
                    break_long_words=False,
                    break_on_hyphens=False
                )
            )

    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]

        if linhas:
            linhas[-1] = linhas[-1].rstrip(".") + "..."

    return "\n".join(linhas), font_min


def desenhar_texto_ajustado(
    ax,
    texto,
    x=0.04,
    y=0.68,
    largura=60,
    font_max=12,
    font_min=7,
    max_linhas=8,
    cor=CINZA_ESCURO,
    linhaspacing=1.15
):
    texto_final, fonte = preparar_linhas(
        texto=texto,
        largura=largura,
        font_max=font_max,
        font_min=font_min,
        max_linhas=max_linhas
    )

    ax.text(
        x,
        y,
        texto_mpl(texto_final),
        fontsize=fonte,
        color=cor,
        va="top",
        linespacing=linhaspacing,
        transform=ax.transAxes
    )


def desenhar_imagem_produto(ax, imagem):
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)

    if imagem is None:
        ax.text(
            0.5,
            0.5,
            "Sem foto cadastrada",
            ha="center",
            va="center",
            color=CINZA_TEXTO,
            fontsize=13,
            transform=ax.transAxes
        )
        return

    ax.imshow(imagem)
    ax.set_aspect("auto")


def salvar_figura(fig):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    caminho = temp.name
    temp.close()

    fig.savefig(
        caminho,
        dpi=220,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
        pad_inches=0.02
    )

    plt.close(fig)

    return caminho


# =========================================================
# POST 1 - COTAÇÃO E COMPORTAMENTO DO PREÇO
# =========================================================
def gerar_post_produto_cotacao_png(
    produto_nome,
    produto_classe,
    produto_unidade,
    data_inicial,
    data_final,
    info_produto,
    indicadores,
    df_periodo
):
    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(CINZA_FUNDO)

    gs = fig.add_gridspec(
        nrows=34,
        ncols=12,
        left=0.05,
        right=0.95,
        top=0.98,
        bottom=0.045,
        hspace=1.10,
        wspace=0.85
    )

    linha2 = (
        f"Classe: {produto_classe}  |  Unidade: {produto_unidade}  |  "
        f"Período: {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
    )

    desenhar_cabecalho(
        fig,
        gs,
        produto_nome,
        linha2
    )

    # KPIs
    kpi_titulos = [
        "PREÇO MÉDIO/KG",
        "MENOR PREÇO/KG",
        "MAIOR PREÇO/KG",
        "VARIAÇÃO"
    ]

    kpi_valores = [
        formatar_moeda(indicadores["preco_medio"]),
        formatar_moeda(indicadores["preco_minimo"]),
        formatar_moeda(indicadores["preco_maximo"]),
        formatar_percentual(indicadores["variacao"])
    ]

    kpi_subs = [
        "no período analisado",
        "menor valor observado",
        "maior valor observado",
        produto_nome
    ]

    kpi_axes = [
        fig.add_subplot(gs[5:8, 0:3]),
        fig.add_subplot(gs[5:8, 3:6]),
        fig.add_subplot(gs[5:8, 6:9]),
        fig.add_subplot(gs[5:8, 9:12]),
    ]

    for i, ax in enumerate(kpi_axes):
        adicionar_cartao(fig, ax)
        ax.axis("off")

        cor_lateral = AZUL_DESTAQUE

        if kpi_titulos[i] == "VARIAÇÃO" and indicadores["variacao"] < 0:
            cor_lateral = VERMELHO

        ax.add_line(
            plt.Line2D(
                [0.06, 0.06],
                [0.22, 0.78],
                transform=ax.transAxes,
                color=cor_lateral,
                linewidth=4.2,
                solid_capstyle="round"
            )
        )

        ax.text(
            0.12,
            0.70,
            kpi_titulos[i],
            fontsize=11.8,
            color=cor_lateral,
            fontweight="bold",
            transform=ax.transAxes
        )

        ax.text(
            0.12,
            0.43,
            kpi_valores[i],
            fontsize=20,
            color=CINZA_ESCURO,
            fontweight="bold",
            transform=ax.transAxes
        )

        ax.text(
            0.12,
            0.18,
            limitar_texto(kpi_subs[i], 24),
            fontsize=10,
            color=CINZA_TEXTO,
            fontweight="bold",
            transform=ax.transAxes
        )

    # Foto
    foto_url = info_produto.get("foto_url", "")
    imagem = baixar_imagem_url(foto_url)

    ax_foto = fig.add_subplot(gs[9:16, 0:4])
    adicionar_cartao(fig, ax_foto)
    desenhar_imagem_produto(ax_foto, imagem)

    # Descrição curta
    ax_desc = fig.add_subplot(gs[9:16, 4:12])
    adicionar_cartao(fig, ax_desc)
    ax_desc.axis("off")

    desenhar_titulo_secao(ax_desc, "Descrição do produto", tamanho=19)

    descricao_curta = obter_campo(info_produto, "descricao_curta")

    desenhar_texto_ajustado(
        ax_desc,
        descricao_curta,
        x=0.04,
        y=0.66,
        largura=72,
        font_max=13,
        font_min=8,
        max_linhas=7,
        cor=CINZA_ESCURO
    )

    ax_desc.text(
        0.04,
        0.16,
        texto_mpl(f"Registros analisados: {indicadores['registros']}\nAmplitude: {formatar_moeda(indicadores['amplitude'])}"),
        fontsize=11.5,
        color=CINZA_TEXTO,
        fontweight="bold",
        va="bottom",
        transform=ax_desc.transAxes
    )

    # Gráfico
    ax_graf = fig.add_subplot(gs[17:24, :])
    adicionar_cartao(fig, ax_graf)
    ax_graf.set_facecolor("none")

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
        color=AZUL_DESTAQUE,
        linestyle=estilo_linha,
        marker=marcador,
        linewidth=2.5,
        markersize=6,
        markerfacecolor="white",
        markeredgecolor=AZUL_DESTAQUE,
        markeredgewidth=1.4,
        label="Preço por kg"
    )

    media_periodo = df_grafico["valor_kg"].mean()

    ax_graf.axhline(
        media_periodo,
        color=VERMELHO,
        linestyle="--",
        linewidth=1.5,
        alpha=0.95,
        label="Média do período"
    )

    ax_graf.set_title(
        "Comportamento dos preços no período",
        fontsize=18,
        fontweight="bold",
        color=AZUL_TEXTO,
        pad=14
    )

    ax_graf.grid(True, alpha=0.18, color="#8092A3", linestyle=":")
    ax_graf.set_axisbelow(True)

    ax_graf.tick_params(axis="x", colors=CINZA_TEXTO, rotation=28, labelsize=10)
    ax_graf.tick_params(axis="y", colors=CINZA_TEXTO, labelsize=10)

    ax_graf.set_ylabel("Preço por Kg (R$)", color=CINZA_TEXTO, fontsize=11)

    ax_graf.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax_graf.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

    ax_graf.legend(
        loc="best",
        fontsize=9.5,
        frameon=False
    )

    for spine in ax_graf.spines.values():
        spine.set_visible(False)

    # Resumo
    ax_resumo = fig.add_subplot(gs[25:32, :])
    adicionar_cartao(fig, ax_resumo)
    ax_resumo.axis("off")

    desenhar_titulo_secao(ax_resumo, "Resumo da análise", tamanho=19)

    texto_insights = formatar_bullets(
        gerar_insights_produto_curto(produto_nome, indicadores),
        largura=112
    )

    desenhar_texto_ajustado(
        ax_resumo,
        texto_insights,
        x=0.04,
        y=0.63,
        largura=118,
        font_max=12,
        font_min=7,
        max_linhas=8,
        cor=CINZA_ESCURO
    )

    fig.text(
        0.5,
        0.018,
        "Acompanhe a cotação diária do Mercado do Produtor de Juazeiro\n@mercadodoprodutorjuazeiro",
        ha="center",
        va="bottom",
        fontsize=10.5,
        color=AZUL_TEXTO,
        fontweight="bold"
    )

    return salvar_figura(fig)


# =========================================================
# POST 2 - INFORMAÇÕES COMPLETAS DO PRODUTO
# =========================================================
def gerar_post_produto_informacoes_png(
    produto_nome,
    produto_classe,
    produto_unidade,
    data_inicial,
    data_final,
    info_produto,
    indicadores,
    df_periodo
):
    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(CINZA_FUNDO)

    gs = fig.add_gridspec(
        nrows=42,
        ncols=12,
        left=0.05,
        right=0.95,
        top=0.98,
        bottom=0.075,
        hspace=1.28,
        wspace=0.85
    )

    linha2 = f"Informações do produto  |  Classe: {produto_classe}  |  Unidade: {produto_unidade}"

    desenhar_cabecalho(
        fig,
        gs,
        produto_nome,
        linha2
    )

    # Foto + descrição completa
    foto_url = info_produto.get("foto_url", "")
    imagem = baixar_imagem_url(foto_url)

    ax_foto = fig.add_subplot(gs[5:13, 0:4])
    adicionar_cartao(fig, ax_foto)
    desenhar_imagem_produto(ax_foto, imagem)

    ax_desc = fig.add_subplot(gs[5:13, 4:12])
    adicionar_cartao(fig, ax_desc)
    ax_desc.axis("off")

    desenhar_titulo_secao(ax_desc, "Descrição completa", tamanho=18)

    descricao_completa = obter_campo(info_produto, "descricao_completa")

    if descricao_completa == "Não informado.":
        descricao_completa = obter_campo(info_produto, "descricao_curta")

    desenhar_texto_ajustado(
        ax_desc,
        descricao_completa,
        x=0.04,
        y=0.66,
        largura=76,
        font_max=11,
        font_min=6,
        max_linhas=11,
        cor=CINZA_ESCURO,
        linhaspacing=1.08
    )

    # Vitaminas
    ax_vit = fig.add_subplot(gs[14:19, 0:6])
    adicionar_cartao(fig, ax_vit)
    ax_vit.axis("off")

    desenhar_titulo_secao(ax_vit, "Vitaminas", tamanho=16)

    desenhar_texto_ajustado(
        ax_vit,
        obter_campo(info_produto, "vitaminas"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=10,
        font_min=6,
        max_linhas=7,
        cor=CINZA_ESCURO,
        linhaspacing=1.06
    )

    # Minerais
    ax_min = fig.add_subplot(gs[14:19, 6:12])
    adicionar_cartao(fig, ax_min)
    ax_min.axis("off")

    desenhar_titulo_secao(ax_min, "Minerais", tamanho=16)

    desenhar_texto_ajustado(
        ax_min,
        obter_campo(info_produto, "minerais"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=10,
        font_min=6,
        max_linhas=7,
        cor=CINZA_ESCURO,
        linhaspacing=1.06
    )

    # Benefícios
    ax_ben = fig.add_subplot(gs[20:25, 0:6])
    adicionar_cartao(fig, ax_ben)
    ax_ben.axis("off")

    desenhar_titulo_secao(ax_ben, "Benefícios", tamanho=16)

    desenhar_texto_ajustado(
        ax_ben,
        obter_campo(info_produto, "beneficios"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=10,
        font_min=6,
        max_linhas=7,
        cor=CINZA_ESCURO,
        linhaspacing=1.06
    )

    # Informação nutricional
    ax_info_nutri = fig.add_subplot(gs[20:25, 6:12])
    adicionar_cartao(fig, ax_info_nutri)
    ax_info_nutri.axis("off")

    desenhar_titulo_secao(ax_info_nutri, "Informação nutricional", tamanho=16)

    desenhar_texto_ajustado(
        ax_info_nutri,
        obter_campo(info_produto, "informacao_nutricional"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=10,
        font_min=6,
        max_linhas=7,
        cor=CINZA_ESCURO,
        linhaspacing=1.06
    )

    # Uso culinário
    ax_uso = fig.add_subplot(gs[26:31, 0:6])
    adicionar_cartao(fig, ax_uso)
    ax_uso.axis("off")

    desenhar_titulo_secao(ax_uso, "Uso culinário", tamanho=16)

    desenhar_texto_ajustado(
        ax_uso,
        obter_campo(info_produto, "uso_culinario"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=9,
        font_min=5,
        max_linhas=8,
        cor=CINZA_ESCURO,
        linhaspacing=1.03
    )

    # Sazonalidade
    ax_saz = fig.add_subplot(gs[26:31, 6:12])
    adicionar_cartao(fig, ax_saz)
    ax_saz.axis("off")

    desenhar_titulo_secao(ax_saz, "Sazonalidade", tamanho=16)

    desenhar_texto_ajustado(
        ax_saz,
        obter_campo(info_produto, "sazonalidade"),
        x=0.04,
        y=0.62,
        largura=54,
        font_max=9,
        font_min=5,
        max_linhas=8,
        cor=CINZA_ESCURO,
        linhaspacing=1.03
    )

    # Comportamento no Ceasa
    ax_comportamento = fig.add_subplot(gs[32:36, :])
    adicionar_cartao(fig, ax_comportamento)
    ax_comportamento.axis("off")

    desenhar_titulo_secao(ax_comportamento, "Comportamento no Ceasa", tamanho=15)

    desenhar_texto_ajustado(
        ax_comportamento,
        obter_campo(info_produto, "comportamento_ceasa"),
        x=0.04,
        y=0.55,
        largura=118,
        font_max=8.8,
        font_min=5,
        max_linhas=5,
        cor=CINZA_ESCURO,
        linhaspacing=1.02
    )

    # Observações
    ax_obs = fig.add_subplot(gs[37:41, :])
    adicionar_cartao(fig, ax_obs)
    ax_obs.axis("off")

    desenhar_titulo_secao(ax_obs, "Observações", tamanho=15)

    desenhar_texto_ajustado(
        ax_obs,
        obter_campo(info_produto, "observacoes"),
        x=0.04,
        y=0.55,
        largura=118,
        font_max=8.8,
        font_min=5,
        max_linhas=5,
        cor=CINZA_ESCURO,
        linhaspacing=1.02
    )

    fig.text(
        0.5,
        0.025,
        "Informações cadastradas no Sistema de Cotação da AMA\\n@mercadodoprodutorjuazeiro",
        ha="center",
        va="bottom",
        fontsize=9.4,
        color=AZUL_TEXTO,
        fontweight="bold"
    )

    return salvar_figura(fig)


# =========================================================
# GERADOR DOS DOIS POSTS
# =========================================================
def gerar_posts_produto_png(
    produto_nome,
    produto_classe,
    produto_unidade,
    data_inicial,
    data_final,
    info_produto,
    indicadores,
    df_periodo
):
    post_1 = gerar_post_produto_cotacao_png(
        produto_nome=produto_nome,
        produto_classe=produto_classe,
        produto_unidade=produto_unidade,
        data_inicial=data_inicial,
        data_final=data_final,
        info_produto=info_produto,
        indicadores=indicadores,
        df_periodo=df_periodo
    )

    post_2 = gerar_post_produto_informacoes_png(
        produto_nome=produto_nome,
        produto_classe=produto_classe,
        produto_unidade=produto_unidade,
        data_inicial=data_inicial,
        data_final=data_final,
        info_produto=info_produto,
        indicadores=indicadores,
        df_periodo=df_periodo
    )

    return post_1, post_2


def criar_zip_posts(produto_nome, caminho_post_1, caminho_post_2):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    caminho_zip = temp.name
    temp.close()

    nome_base = nome_arquivo_seguro(produto_nome)

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(caminho_post_1, f"{nome_base}_post_1_cotacao.png")
        zipf.write(caminho_post_2, f"{nome_base}_post_2_informacoes.png")

    return caminho_zip
