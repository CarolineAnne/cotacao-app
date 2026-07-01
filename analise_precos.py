import io
import re
import unicodedata

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime

from dados_utils import carregar_todas_cotacoes
from utils import corrigir_classe
from graficos_utils import (
    obter_estilo_linha,
    aplicar_estilo_impressao
)
from pdf_utils import gerar_pdf_analise_precos, gerar_pdf_produto_analise

from observacoes_produtos import (
    carregar_observacoes_produto_periodo,
    carregar_observacoes_periodo
)

def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):.2f}".replace(".", ",")
    except Exception:
        return "R$ 0,00"


def formatar_numero(valor):
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def formatar_percentual(valor):
    try:
        return f"{float(valor):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"
    
ORDEM_CLASSES_RELATORIO = {
    "Hortaliças": 1,
    "Frutas": 2,
    "Especiarias": 3,
    "Cereais": 4
}


def ordenar_classes_relatorio(df, coluna_classe="classe", coluna_produto="produto", coluna_mes=None):
    df = df.copy()

    if df.empty:
        return df

    if coluna_classe in df.columns:
        df["_ordem_classe"] = df[coluna_classe].map(ORDEM_CLASSES_RELATORIO).fillna(99)
    else:
        df["_ordem_classe"] = 99

    colunas_ordenacao = []
    ordem_ascendente = []

    if coluna_mes is not None and coluna_mes in df.columns:
        df["_mes_ordem"] = pd.to_datetime(
            "01/" + df[coluna_mes].astype(str),
            format="%d/%m/%Y",
            errors="coerce"
        )

        colunas_ordenacao.append("_mes_ordem")
        ordem_ascendente.append(True)

    colunas_ordenacao.extend(["_ordem_classe", coluna_produto])
    ordem_ascendente.extend([True, True])

    df = df.sort_values(
        by=colunas_ordenacao,
        ascending=ordem_ascendente
    )

    colunas_remover = ["_ordem_classe"]

    if "_mes_ordem" in df.columns:
        colunas_remover.append("_mes_ordem")

    df = df.drop(columns=colunas_remover)

    return df


def classificar_variacao(valor):
    try:
        valor = float(valor)
    except Exception:
        return "➖ Estável"

    if valor > 0:
        return "📈 Alta"
    elif valor < 0:
        return "📉 Queda"
    else:
        return "➖ Estável"

def classificar_alerta_variacao(valor):
    try:
        valor = float(valor)
    except Exception:
        return "Sem classificação"

    if valor >= 60:
        return "🚨 Alta crítica"

    elif valor >= 30:
        return "⚠️ Alta acentuada"

    elif valor >= 10:
        return "🟡 Alta moderada"

    elif valor <= -30:
        return "🔵 Queda acentuada"

    elif valor <= -10:
        return "📉 Queda relevante"

    else:
        return "✅ Variação normal"
    
def mostrar_legenda_variacao():
    legenda = pd.DataFrame([
        {
            "Variação": "Acima de 60%",
            "Classificação": "🚨 Alta crítica"
        },
        {
            "Variação": "De 30% a 59,99%",
            "Classificação": "⚠️ Alta acentuada"
        },
        {
            "Variação": "De 10% a 29,99%",
            "Classificação": "🟡 Alta moderada"
        },
        {
            "Variação": "De -10% a -29,99%",
            "Classificação": "📉 Queda relevante"
        },
        {
            "Variação": "Abaixo de -30%",
            "Classificação": "🔵 Queda acentuada"
        },
        {
            "Variação": "Entre -9,99% e 9,99%",
            "Classificação": "✅ Variação normal"
        }
    ])

    st.markdown("#### 📌 Legenda de classificação das variações")
    st.dataframe(
        legenda,
        use_container_width=True,
        hide_index=True
    )


# ================= VOLUME MENSAL ESTIMADO =================
def normalizar_produto_volume(valor):
    texto = str(valor).strip().upper()
    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip()

    return texto


def carregar_volumes_ano_anterior(supabase):
    resp = (
        supabase
        .table("volumes_ano_anterior")
        .select("*")
        .execute()
    )

    return pd.DataFrame(resp.data or [])


def salvar_volume_mensal_confirmado(supabase, volume_mensal, classe_sel="Todas"):
    """
    Salva o volume calculado/confirmado como volume oficial do mês atual.

    A mesma tabela volumes_ano_anterior é usada como histórico de volumes por ano/mês.
    Quando o mês atual é salvo aqui, o cálculo passa a usar esse volume confirmado
    e deixa de recalcular esse mês com base no ano anterior.
    """

    if volume_mensal is None or volume_mensal.empty:
        raise ValueError("Não há volume mensal para salvar.")

    df_salvar = volume_mensal.copy()

    colunas_obrigatorias = [
        "Mês-Ano",
        "Classe",
        "Produto",
        "Quantidade (kg)"
    ]

    for coluna in colunas_obrigatorias:
        if coluna not in df_salvar.columns:
            raise ValueError(f"Coluna obrigatória não encontrada: {coluna}")

    df_salvar["data_mes"] = pd.to_datetime(
        "01/" + df_salvar["Mês-Ano"].astype(str),
        format="%d/%m/%Y",
        errors="coerce"
    )

    df_salvar = df_salvar.dropna(subset=["data_mes"]).copy()

    if df_salvar.empty:
        raise ValueError("Nenhum mês válido foi encontrado para salvar.")

    df_salvar["ano"] = df_salvar["data_mes"].dt.year.astype(int)
    df_salvar["mes"] = df_salvar["data_mes"].dt.month.astype(int)
    df_salvar["classe"] = df_salvar["Classe"].astype(str).str.strip().apply(corrigir_classe)
    df_salvar["produto"] = df_salvar["Produto"].astype(str).str.strip().str.upper()
    df_salvar["quantidade_kg"] = pd.to_numeric(
        df_salvar["Quantidade (kg)"],
        errors="coerce"
    )

    df_salvar = df_salvar.dropna(subset=["quantidade_kg"])
    df_salvar = df_salvar[df_salvar["quantidade_kg"] > 0].copy()

    if classe_sel != "Todas":
        df_salvar = df_salvar[df_salvar["classe"] == classe_sel].copy()

    if df_salvar.empty:
        raise ValueError("Nenhum volume válido foi encontrado para salvar.")

    # Evita duplicidade se houver produto repetido no cálculo.
    df_salvar = (
        df_salvar
        .groupby(["ano", "mes", "classe", "produto"], as_index=False)["quantidade_kg"]
        .sum()
    )

    meses_salvos = (
        df_salvar[["ano", "mes"]]
        .drop_duplicates()
        .sort_values(["ano", "mes"])
        .to_dict("records")
    )

    # Remove os volumes já existentes do mesmo ano/mês antes de inserir novamente.
    # Isso evita precisar depender de constraint unique no Supabase.
    for item in meses_salvos:
        query = (
            supabase
            .table("volumes_ano_anterior")
            .delete()
            .eq("ano", int(item["ano"]))
            .eq("mes", int(item["mes"]))
        )

        if classe_sel != "Todas":
            query = query.eq("classe", classe_sel)

        query.execute()

    registros = df_salvar[[
        "ano",
        "mes",
        "classe",
        "produto",
        "quantidade_kg"
    ]].to_dict("records")

    # Converte tipos numpy para tipos nativos do Python, aceitos pelo Supabase.
    registros = [
        {
            "ano": int(r["ano"]),
            "mes": int(r["mes"]),
            "classe": str(r["classe"]),
            "produto": str(r["produto"]),
            "quantidade_kg": float(r["quantidade_kg"]),
        }
        for r in registros
    ]

    supabase.table("volumes_ano_anterior").insert(registros).execute()

    meses_txt = [
        f"{str(item['mes']).zfill(2)}/{item['ano']}"
        for item in meses_salvos
    ]

    return len(registros), meses_txt


def volume_mensal_esta_confirmado(volume_mensal):
    """
    Verifica se todos os registros de volume exibidos na tela já foram confirmados no banco.

    A coluna "Confirmado no banco" é a forma principal de checagem.
    A verificação pela coluna "Observação" fica como segurança para versões antigas do DataFrame.
    """

    if volume_mensal is None or volume_mensal.empty:
        return False

    df_check = volume_mensal.copy()

    if "Confirmado no banco" in df_check.columns:
        confirmado = df_check["Confirmado no banco"].fillna(False)

        if confirmado.dtype == object:
            confirmado = confirmado.astype(str).str.lower().isin([
                "true",
                "1",
                "sim",
                "s",
                "yes",
                "y"
            ])

        return bool(confirmado.all())

    if "Observação" in df_check.columns:
        return bool(
            df_check["Observação"]
            .astype(str)
            .str.contains("confirmado no banco", case=False, na=False)
            .all()
        )

    return False


def preparar_precos_mes_volume(df_cotacoes, mes, ano):
    dfp = df_cotacoes.copy()

    if dfp.empty:
        return pd.DataFrame()

    dfp["data"] = pd.to_datetime(dfp["data"], errors="coerce")
    dfp = dfp.dropna(subset=["data"])

    dfp["mes"] = dfp["data"].dt.month
    dfp["ano"] = dfp["data"].dt.year

    dfp = dfp[
        (dfp["mes"] == int(mes)) &
        (dfp["ano"] == int(ano))
    ].copy()

    if dfp.empty:
        return pd.DataFrame()

    dfp["produto_norm"] = dfp["produto"].apply(normalizar_produto_volume)
    dfp["valor_kg"] = pd.to_numeric(dfp["valor_kg"], errors="coerce")
    dfp["preco_medio"] = pd.to_numeric(dfp["preco_medio"], errors="coerce")

    resumo = (
        dfp
        .groupby("produto_norm", as_index=False)
        .agg(
            produto=("produto", "first"),
            classe=("classe", "first"),
            preco_kg_medio=("valor_kg", "mean"),
            preco_medio_caixa=("preco_medio", "mean")
        )
    )

    return resumo


def gerar_volume_mensal_estimado_analise(
    supabase,
    df_cotacoes,
    meses_ano_atuais,
    classe_sel="Todas",
    kg_por_caminhao=15000,
    sensibilidade_preco=0.01,
    crescimento_minimo_classe=None,
    ajuste_volume_mensal_percentual=0.0
):
    """
    Estima o volume mensal usando uma regra simples:

    1. Se o mês atual já tiver volume salvo na tabela volumes_ano_anterior,
       usa esse volume confirmado e não recalcula pelo ano anterior.
    2. Se o mês atual ainda não tiver volume salvo, calcula com base no mesmo mês
       do ano anterior, no ajuste mensal informado e na variação do preço/kg.
    3. A regra de preço é assimétrica:
       - preço subiu: volume cai pouco;
       - preço caiu: volume sobe em maior proporção;
       - preço insuficiente: usa o ajuste geral do mês.
    """

    df_volumes = carregar_volumes_ano_anterior(supabase)

    if df_volumes.empty:
        raise ValueError("Nenhum volume foi encontrado na tabela volumes_ano_anterior.")

    df_volumes = df_volumes.copy()
    df_volumes["ano"] = pd.to_numeric(df_volumes["ano"], errors="coerce")
    df_volumes["mes"] = pd.to_numeric(df_volumes["mes"], errors="coerce")
    df_volumes["quantidade_kg"] = pd.to_numeric(df_volumes["quantidade_kg"], errors="coerce")

    df_volumes = df_volumes.dropna(subset=["ano", "mes", "quantidade_kg"])
    df_volumes = df_volumes[df_volumes["quantidade_kg"] > 0].copy()

    df_volumes["ano"] = df_volumes["ano"].astype(int)
    df_volumes["mes"] = df_volumes["mes"].astype(int)
    df_volumes["classe"] = df_volumes["classe"].astype(str).str.strip().apply(corrigir_classe)
    df_volumes["produto"] = df_volumes["produto"].astype(str).str.strip().str.upper()
    df_volumes["produto_norm"] = df_volumes["produto"].apply(normalizar_produto_volume)

    if classe_sel != "Todas":
        df_volumes = df_volumes[df_volumes["classe"] == classe_sel].copy()

    # Garante uma linha por produto/mês, mesmo que exista duplicidade antiga no banco.
    df_volumes = (
        df_volumes
        .groupby(["ano", "mes", "classe", "produto", "produto_norm"], as_index=False)["quantidade_kg"]
        .sum()
    )

    partes = []
    avisos = []

    ajuste_geral_mes = 1 + (float(ajuste_volume_mensal_percentual) / 100)
    ajuste_geral_mes = max(0, ajuste_geral_mes)

    for mes_ano in meses_ano_atuais:
        data_mes = pd.to_datetime(
            "01/" + str(mes_ano),
            format="%d/%m/%Y",
            errors="coerce"
        )

        if pd.isna(data_mes):
            continue

        mes_atual = int(data_mes.month)
        ano_atual = int(data_mes.year)
        ano_anterior = ano_atual - 1

        vol_anterior = df_volumes[
            (df_volumes["mes"] == mes_atual) &
            (df_volumes["ano"] == ano_anterior)
        ].copy()

        vol_atual_confirmado = df_volumes[
            (df_volumes["mes"] == mes_atual) &
            (df_volumes["ano"] == ano_atual)
        ].copy()

        tem_volume_confirmado = not vol_atual_confirmado.empty

        if vol_anterior.empty and not tem_volume_confirmado:
            avisos.append(f"Sem volume anterior para {str(mes_atual).zfill(2)}/{ano_anterior}.")
            continue

        precos_anterior = preparar_precos_mes_volume(
            df_cotacoes,
            mes=mes_atual,
            ano=ano_anterior
        )

        precos_atual = preparar_precos_mes_volume(
            df_cotacoes,
            mes=mes_atual,
            ano=ano_atual
        )

        if precos_atual.empty:
            avisos.append(f"Sem preço atual para {str(mes_atual).zfill(2)}/{ano_atual}.")
            continue

        if precos_anterior.empty:
            avisos.append(
                f"Sem preço anterior para {str(mes_atual).zfill(2)}/{ano_anterior}. "
                "O cálculo desse mês foi ignorado."
            )
            continue

        precos_anterior = precos_anterior.rename(columns={
            "preco_kg_medio": "preco_kg_anterior",
            "preco_medio_caixa": "preco_medio_caixa_anterior"
        })

        precos_atual = precos_atual.rename(columns={
            "preco_kg_medio": "preco_kg_atual",
            "preco_medio_caixa": "preco_medio_caixa_atual"
        })

        if tem_volume_confirmado:
            # Quando já existe volume do mês atual no banco, ele é a verdade do cálculo.
            base = vol_atual_confirmado[[
                "classe",
                "produto",
                "produto_norm",
                "quantidade_kg"
            ]].copy()

            base = base.rename(columns={
                "quantidade_kg": "quantidade_confirmada_kg"
            })

            if not vol_anterior.empty:
                vol_anterior_resumo = (
                    vol_anterior
                    .groupby("produto_norm", as_index=False)
                    .agg(quantidade_ano_anterior_kg=("quantidade_kg", "sum"))
                )

                base = base.merge(
                    vol_anterior_resumo,
                    on="produto_norm",
                    how="left"
                )
            else:
                base["quantidade_ano_anterior_kg"] = 0

            base["quantidade_ano_anterior_kg"] = pd.to_numeric(
                base["quantidade_ano_anterior_kg"],
                errors="coerce"
            ).fillna(0)

            base["volume_confirmado_banco"] = True

            avisos.append(
                f"{mes_ano}: já existe volume confirmado no banco. "
                "O sistema usou esses valores e não recalculou pelo ano anterior."
            )

        else:
            # Quando ainda não existe volume atual, usa o ano anterior como base.
            base = vol_anterior[[
                "classe",
                "produto",
                "produto_norm",
                "quantidade_kg"
            ]].copy()

            base["quantidade_ano_anterior_kg"] = base["quantidade_kg"]
            base["volume_confirmado_banco"] = False

        base = base.merge(
            precos_anterior[["produto_norm", "preco_kg_anterior", "preco_medio_caixa_anterior"]],
            on="produto_norm",
            how="left"
        )

        base = base.merge(
            precos_atual[["produto_norm", "preco_kg_atual", "preco_medio_caixa_atual"]],
            on="produto_norm",
            how="left"
        )

        base["preco_kg_anterior"] = pd.to_numeric(base["preco_kg_anterior"], errors="coerce")
        base["preco_kg_atual"] = pd.to_numeric(base["preco_kg_atual"], errors="coerce")

        base["sem_preco_anterior"] = (
            base["preco_kg_anterior"].isna() |
            (base["preco_kg_anterior"] <= 0)
        )

        base["sem_preco_atual"] = (
            base["preco_kg_atual"].isna() |
            (base["preco_kg_atual"] <= 0)
        )

        base["sem_preco_suficiente"] = (
            base["sem_preco_anterior"] |
            base["sem_preco_atual"]
        )

        produtos_sem_preco = base[
            base["sem_preco_suficiente"]
        ]["produto"].dropna().unique().tolist()

        if produtos_sem_preco:
            avisos.append(
                f"Produtos sem preço suficiente em {mes_ano}; "
                "eles foram mantidos no cálculo usando preço estimado da classe/geral: " +
                ", ".join(produtos_sem_preco[:10])
            )

        # Preenche preços ausentes com média da classe; se ainda faltar, usa média geral;
        # se ainda faltar, usa o preço disponível do outro ano.
        media_atual_classe = (
            base[~base["sem_preco_atual"]]
            .groupby("classe")["preco_kg_atual"]
            .mean()
            .to_dict()
        )

        media_anterior_classe = (
            base[~base["sem_preco_anterior"]]
            .groupby("classe")["preco_kg_anterior"]
            .mean()
            .to_dict()
        )

        media_atual_geral = base.loc[~base["sem_preco_atual"], "preco_kg_atual"].mean()
        media_anterior_geral = base.loc[~base["sem_preco_anterior"], "preco_kg_anterior"].mean()

        base.loc[base["sem_preco_atual"], "preco_kg_atual"] = base.loc[
            base["sem_preco_atual"],
            "classe"
        ].map(media_atual_classe)

        base.loc[base["sem_preco_anterior"], "preco_kg_anterior"] = base.loc[
            base["sem_preco_anterior"],
            "classe"
        ].map(media_anterior_classe)

        base.loc[
            base["preco_kg_atual"].isna() | (base["preco_kg_atual"] <= 0),
            "preco_kg_atual"
        ] = media_atual_geral

        base.loc[
            base["preco_kg_anterior"].isna() | (base["preco_kg_anterior"] <= 0),
            "preco_kg_anterior"
        ] = media_anterior_geral

        base.loc[
            base["preco_kg_atual"].isna() | (base["preco_kg_atual"] <= 0),
            "preco_kg_atual"
        ] = base["preco_kg_anterior"]

        base.loc[
            base["preco_kg_anterior"].isna() | (base["preco_kg_anterior"] <= 0),
            "preco_kg_anterior"
        ] = base["preco_kg_atual"]

        base = base[
            (base["preco_kg_anterior"] > 0) &
            (base["preco_kg_atual"] > 0)
        ].copy()

        if tem_volume_confirmado:
            base = base[base["quantidade_confirmada_kg"] > 0].copy()
        else:
            base = base[base["quantidade_ano_anterior_kg"] > 0].copy()

        if base.empty:
            continue

        base["valor_ano_anterior"] = (
            base["quantidade_ano_anterior_kg"] * base["preco_kg_anterior"]
        )

        base["variacao_preco"] = (
            base["preco_kg_atual"] / base["preco_kg_anterior"]
        ) - 1

        base.loc[base["sem_preco_suficiente"], "variacao_preco"] = 0
        base["variacao_preco_percentual"] = base["variacao_preco"] * 100

        if tem_volume_confirmado:
            base["fator_geral_mes"] = 1.00
            base["fator_preco"] = 1.00
            base["fator_volume"] = 1.00
            base["quantidade_estimada_kg"] = base["quantidade_confirmada_kg"]

            base["observacao_volume"] = "Volume atual confirmado no banco de dados"

        else:
            # ================= CÁLCULO ASSIMÉTRICO DO VOLUME =================
            # Se o preço subiu, o volume cai pouco.
            # Se o preço caiu, o volume sobe em maior proporção.
            # Se não tiver preço suficiente, considera apenas o ajuste geral do mês.
            base["fator_preco"] = 1.00

            mask_preco_subiu = (
                (base["variacao_preco"] > 0) &
                (~base["sem_preco_suficiente"])
            )

            mask_preco_caiu = (
                (base["variacao_preco"] < 0) &
                (~base["sem_preco_suficiente"])
            )

            mask_sem_preco = base["sem_preco_suficiente"]

            queda_volume = (
                base.loc[mask_preco_subiu, "variacao_preco"].abs() * 0.08
            )

            queda_volume = queda_volume.clip(
                lower=0.005,  # queda mínima de 0,5%
                upper=0.05    # queda máxima de 5%
            )

            base.loc[mask_preco_subiu, "fator_preco"] = 1 - queda_volume

            aumento_volume = (
                base.loc[mask_preco_caiu, "variacao_preco"].abs() * 0.60
            )

            aumento_volume = aumento_volume.clip(
                lower=0.03,   # aumento mínimo de 3%
                upper=0.25    # aumento máximo de 25%
            )

            base.loc[mask_preco_caiu, "fator_preco"] = 1 + aumento_volume

            base.loc[mask_sem_preco, "fator_preco"] = 1.00
            base.loc[mask_sem_preco, "variacao_preco_percentual"] = 0

            base["fator_geral_mes"] = ajuste_geral_mes
            base["fator_geral_aplicado"] = base["fator_geral_mes"]

            # Se o ajuste mensal for positivo, ele não transforma produto com preço maior em aumento.
            if ajuste_geral_mes > 1:
                base.loc[mask_preco_subiu, "fator_geral_aplicado"] = 1.00

            base["fator_volume"] = (
                base["fator_geral_aplicado"] *
                base["fator_preco"]
            )

            base["fator_volume"] = base["fator_volume"].clip(
                lower=0.05,
                upper=3.00
            )

            base["quantidade_estimada_kg"] = (
                base["quantidade_ano_anterior_kg"] * base["fator_volume"]
            )

            base["observacao_volume"] = "Ajuste geral do mês + regra assimétrica de preço"

            base.loc[
                mask_preco_subiu,
                "observacao_volume"
            ] = "Preço subiu: volume reduzido levemente"

            base.loc[
                mask_preco_caiu,
                "observacao_volume"
            ] = "Preço caiu: volume aumentado em maior proporção"

            base.loc[
                mask_sem_preco,
                "observacao_volume"
            ] = "Preço insuficiente: aplicado ajuste geral do mês"

        base["valor_comercializado"] = (
            base["quantidade_estimada_kg"] * base["preco_kg_atual"]
        )

        base["variacao_volume_percentual"] = base.apply(
            lambda row: (
                ((row["quantidade_estimada_kg"] / row["quantidade_ano_anterior_kg"]) - 1) * 100
                if row["quantidade_ano_anterior_kg"] > 0 else 0
            ),
            axis=1
        )

        volume_anterior_mes = base["quantidade_ano_anterior_kg"].sum()
        volume_estimado_mes = base["quantidade_estimada_kg"].sum()

        variacao_real_mes = (
            (volume_estimado_mes / volume_anterior_mes) - 1
        ) * 100 if volume_anterior_mes > 0 else 0

        if not tem_volume_confirmado:
            avisos.append(
                f"{mes_ano}: volume estimado com ajuste geral de "
                f"{float(ajuste_volume_mensal_percentual):,.2f}% e variação final de "
                f"{variacao_real_mes:,.2f}% sobre o ano anterior."
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

        total_volume_mes = base["quantidade_estimada_kg"].sum()

        if total_volume_mes <= 0:
            continue

        base["porcentagem"] = (base["quantidade_estimada_kg"] / total_volume_mes) * 100
        base["caminhoes"] = base["quantidade_estimada_kg"] / kg_por_caminhao
        base["mes_ano"] = mes_ano
        base["ano_atual"] = ano_atual
        base["mes_atual"] = mes_atual

        partes.append(base)

    if not partes:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), avisos

    df_final = pd.concat(partes, ignore_index=True)

    df_final = df_final[
        [
            "mes_ano",
            "classe",
            "produto",
            "quantidade_ano_anterior_kg",
            "quantidade_estimada_kg",
            "variacao_volume_percentual",
            "porcentagem",
            "caminhoes",
            "preco_kg_anterior",
            "preco_kg_atual",
            "variacao_preco_percentual",
            "valor_ano_anterior",
            "valor_comercializado",
            "observacao_volume",
            "volume_confirmado_banco"
        ]
    ].copy()

    df_final = df_final.rename(columns={
        "mes_ano": "Mês-Ano",
        "classe": "Classe",
        "produto": "Produto",
        "quantidade_ano_anterior_kg": "Quantidade ano anterior (kg)",
        "quantidade_estimada_kg": "Quantidade (kg)",
        "variacao_volume_percentual": "Variação volume (%)",
        "porcentagem": "Porcentagem (%)",
        "caminhoes": "Caminhões",
        "preco_kg_anterior": "Preço/kg ano anterior",
        "preco_kg_atual": "Preço/kg médio",
        "variacao_preco_percentual": "Variação preço (%)",
        "valor_ano_anterior": "Valor ano anterior",
        "valor_comercializado": "Valor comercializado",
        "observacao_volume": "Observação",
        "volume_confirmado_banco": "Confirmado no banco"
    })

    df_final = ordenar_classes_relatorio(
        df_final,
        coluna_classe="Classe",
        coluna_produto="Produto",
        coluna_mes="Mês-Ano"
    )

    resumo_classe = (
        df_final
        .groupby(["Mês-Ano", "Classe"], as_index=False)
        .agg({
            "Quantidade ano anterior (kg)": "sum",
            "Quantidade (kg)": "sum",
            "Caminhões": "sum",
            "Valor ano anterior": "sum",
            "Valor comercializado": "sum"
        })
    )

    resumo_classe["Variação volume (%)"] = resumo_classe.apply(
        lambda row: (
            ((row["Quantidade (kg)"] / row["Quantidade ano anterior (kg)"]) - 1) * 100
            if row["Quantidade ano anterior (kg)"] > 0 else 0
        ),
        axis=1
    )

    resumo_classe["Crescimento valor (%)"] = resumo_classe.apply(
        lambda row: (
            ((row["Valor comercializado"] / row["Valor ano anterior"]) - 1) * 100
            if row["Valor ano anterior"] > 0 else 0
        ),
        axis=1
    )

    volume_anterior_total = df_final["Quantidade ano anterior (kg)"].sum()
    volume_atual_total = df_final["Quantidade (kg)"].sum()
    valor_anterior_total = df_final["Valor ano anterior"].sum()
    valor_atual_total = df_final["Valor comercializado"].sum()

    resumo_geral = pd.DataFrame([{
        "Volume ano anterior (kg)": volume_anterior_total,
        "Volume total estimado (kg)": volume_atual_total,
        "Variação volume (%)": (
            ((volume_atual_total / volume_anterior_total) - 1) * 100
            if volume_anterior_total > 0 else 0
        ),
        "Caminhões estimados": df_final["Caminhões"].sum(),
        "Valor comercializado estimado": valor_atual_total,
        "Valor ano anterior": valor_anterior_total,
        "Crescimento valor (%)": (
            ((valor_atual_total / valor_anterior_total) - 1) * 100
            if valor_anterior_total > 0 else 0
        )
    }])

    return df_final, resumo_classe, resumo_geral, avisos
def formatar_volume_para_tela(df_volume):
    df_exibir = df_volume.copy()

    colunas_moeda = [
        "Preço/kg médio",
        "Valor comercializado",
        "Preço/kg ano anterior",
        "Valor ano anterior"
    ]

    colunas_numero = [
        "Quantidade (kg)",
        "Porcentagem (%)",
        "Caminhões",
        "Quantidade ano anterior (kg)",
        "Variação volume (%)",
        "Variação preço (%)"
    ]

    for col in colunas_moeda:
        if col in df_exibir.columns:
            df_exibir[col] = df_exibir[col].apply(formatar_moeda)

    for col in colunas_numero:
        if col in df_exibir.columns:
            df_exibir[col] = df_exibir[col].apply(formatar_numero)

    return df_exibir

def tela_analise_precos(supabase):
    st.title("📈 Análise de Preços")

    st.info(
        "Nesta tela você pode analisar variações de preços, ranking de altas e quedas, "
        "histórico por produto e médias mensais."
    )

    # ================= CARREGAR DADOS =================
    try:
        df = carregar_todas_cotacoes(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        return

    if df.empty:
        st.warning("Ainda não há cotações cadastradas para análise.")
        return

    # ================= TRATAMENTO INICIAL =================
    df = df.copy()

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    if df.empty:
        st.warning("Não há datas válidas nas cotações.")
        return

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

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

    # Remove produtos zerados da análise
    df = df[df["preco_medio"] > 0].copy()

    if df.empty:
        st.warning("Não há produtos com preço maior que zero para analisar.")
        return

    # ================= FILTROS =================
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
            key="analise_data_inicial"
        )

    with col2:
        data_final = st.date_input(
            "Data final",
            value=data_max,
            min_value=data_min,
            max_value=data_max,
            key="analise_data_final"
        )

    with col3:
        classes = ["Todas"] + sorted(df["classe"].dropna().unique().tolist())

        classe_sel = st.selectbox(
            "Classe",
            classes,
            key="analise_classe"
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

    produtos_lista = sorted(df_periodo["produto"].dropna().unique().tolist())

    produto_sel = st.selectbox(
        "Produto para análise histórica",
        ["Todos"] + produtos_lista,
        key="analise_produto"
    )

    # ================= RESUMO =================
    st.divider()
    st.subheader("📌 Resumo do período")

    total_produtos = df_periodo["produto"].nunique()
    total_registros = len(df_periodo)
    preco_medio_geral = df_periodo["preco_medio"].mean()
    valor_kg_medio = df_periodo["valor_kg"].mean()

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Produtos analisados", total_produtos)
    m2.metric("Registros de cotação", total_registros)
    m3.metric("Preço médio geral", formatar_moeda(preco_medio_geral))
    m4.metric("Valor/kg médio", formatar_moeda(valor_kg_medio))

    # ================= VARIAÇÃO POR PRODUTO =================
    st.divider()
    st.subheader("📊 Variação por produto no período")

    df_ord = df_periodo.sort_values(["produto", "data"])

    primeira = df_ord.groupby("produto").first().reset_index()
    ultima = df_ord.groupby("produto").last().reset_index()

    comparativo = primeira[
        [
            "produto",
            "classe",
            "unidade",
            "kg",
            "preco_medio",
            "valor_kg",
            "data"
        ]
    ].merge(
        ultima[
            [
                "produto",
                "preco_medio",
                "valor_kg",
                "data"
            ]
        ],
        on="produto",
        suffixes=("_inicial", "_final")
    )

    comparativo["diferenca"] = (
        comparativo["preco_medio_final"] -
        comparativo["preco_medio_inicial"]
    )

    comparativo["variacao_percentual"] = comparativo.apply(
        lambda row: (
            (row["diferenca"] / row["preco_medio_inicial"]) * 100
            if row["preco_medio_inicial"] > 0 else 0
        ),
        axis=1
    )

    comparativo["status"] = comparativo["variacao_percentual"].apply(classificar_variacao)

    comparativo["alerta"] = comparativo["variacao_percentual"].apply(classificar_alerta_variacao)

    comparativo = comparativo.sort_values(
        "variacao_percentual",
        ascending=False
    )

    comparativo_tabela = comparativo.copy()

    comparativo_tabela["data_inicial"] = pd.to_datetime(
        comparativo_tabela["data_inicial"],
        errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    comparativo_tabela["data_final"] = pd.to_datetime(
        comparativo_tabela["data_final"],
        errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    comparativo_tabela["preco_medio_inicial"] = comparativo_tabela["preco_medio_inicial"].apply(formatar_moeda)
    comparativo_tabela["preco_medio_final"] = comparativo_tabela["preco_medio_final"].apply(formatar_moeda)
    comparativo_tabela["valor_kg_inicial"] = comparativo_tabela["valor_kg_inicial"].apply(formatar_moeda)
    comparativo_tabela["valor_kg_final"] = comparativo_tabela["valor_kg_final"].apply(formatar_moeda)
    comparativo_tabela["diferenca"] = comparativo_tabela["diferenca"].apply(formatar_moeda)
    comparativo_tabela["variacao_percentual"] = comparativo_tabela["variacao_percentual"].apply(formatar_percentual)

    comparativo_tabela = comparativo_tabela.rename(columns={
        "produto": "Produto",
        "classe": "Classe",
        "unidade": "Unidade",
        "kg": "Kg",
        "data_inicial": "Data inicial",
        "data_final": "Data final",
        "preco_medio_inicial": "Preço médio inicial",
        "preco_medio_final": "Preço médio final",
        "valor_kg_inicial": "Valor/kg inicial",
        "valor_kg_final": "Valor/kg final",
        "diferenca": "Diferença",
        "variacao_percentual": "Variação %",
        "status": "Status",
        "alerta": "Alerta"
    })

    st.dataframe(comparativo_tabela, use_container_width=True)

    # ================= ALERTAS AUTOMÁTICOS =================
    st.divider()
    st.subheader("🚨 Alertas de Variação")

    mostrar_legenda_variacao()

    alertas = comparativo[
        comparativo["alerta"] != "✅ Variação normal"
    ].copy()

    # Ordena os alertas pela classificação
    ordem_alertas = {
        "🚨 Alta crítica": 1,
        "⚠️ Alta acentuada": 2,
        "🟡 Alta moderada": 3,
        "🔵 Queda acentuada": 4,
        "📉 Queda relevante": 5,
        "✅ Variação normal": 6
    }

    alertas["_ordem_alerta"] = alertas["alerta"].map(ordem_alertas).fillna(99)

    alertas = alertas.sort_values(
        by=["_ordem_alerta", "classe", "produto"],
        ascending=[True, True, True]
    ).drop(columns=["_ordem_alerta"])

    if alertas.empty:
        st.success("Nenhum alerta relevante encontrado no período selecionado.")
    else:
        total_alertas = len(alertas)
        altas_criticas = len(alertas[alertas["alerta"] == "🚨 Alta crítica"])
        altas_acentuadas = len(alertas[alertas["alerta"] == "⚠️ Alta acentuada"])
        quedas_acentuadas = len(alertas[alertas["alerta"] == "🔵 Queda acentuada"])

        a1, a2, a3, a4 = st.columns(4)

        a1.metric("Total de alertas", total_alertas)
        a2.metric("Altas críticas", altas_criticas)
        a3.metric("Altas acentuadas", altas_acentuadas)
        a4.metric("Quedas acentuadas", quedas_acentuadas)

        alertas_tabela = alertas.copy()

        alertas_tabela["data_inicial"] = pd.to_datetime(
            alertas_tabela["data_inicial"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        alertas_tabela["data_final"] = pd.to_datetime(
            alertas_tabela["data_final"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        alertas_tabela["preco_medio_inicial"] = alertas_tabela["preco_medio_inicial"].apply(formatar_moeda)
        alertas_tabela["preco_medio_final"] = alertas_tabela["preco_medio_final"].apply(formatar_moeda)
        alertas_tabela["diferenca"] = alertas_tabela["diferenca"].apply(formatar_moeda)
        alertas_tabela["variacao_percentual"] = alertas_tabela["variacao_percentual"].apply(formatar_percentual)

        alertas_tabela = alertas_tabela.rename(columns={
            "produto": "Produto",
            "classe": "Classe",
            "unidade": "Unidade",
            "kg": "Kg",
            "data_inicial": "Data inicial",
            "data_final": "Data final",
            "preco_medio_inicial": "Preço médio inicial",
            "preco_medio_final": "Preço médio final",
            "diferenca": "Diferença",
            "variacao_percentual": "Variação %",
            "status": "Status",
            "alerta": "Alerta"
        })

        colunas_alerta = [
            "Produto",
            "Classe",
            "Unidade",
            "Kg",
            "Data inicial",
            "Data final",
            "Preço médio inicial",
            "Preço médio final",
            "Diferença",
            "Variação %",
            "Status",
            "Alerta"
        ]

        st.dataframe(
            alertas_tabela[colunas_alerta],
            use_container_width=True
        )

        st.warning(
            "Produtos com alerta devem ser conferidos com atenção, pois podem indicar "
            "aumento expressivo, queda forte, baixa oferta, mudança de fornecedor ou possível erro de digitação."
        )

    # ================= RANKINGS =================
    st.divider()
    st.subheader("🏆 Ranking de maiores altas e quedas")

    ranking_altas = comparativo[
        comparativo["variacao_percentual"] > 0
    ].sort_values("variacao_percentual", ascending=False).head(10)

    ranking_quedas = comparativo[
        comparativo["variacao_percentual"] < 0
    ].sort_values("variacao_percentual", ascending=True).head(10)

    col_altas, col_quedas = st.columns(2)

    with col_altas:
        st.markdown("### 📈 Maiores altas")

        if ranking_altas.empty:
            st.info("Nenhum produto com alta no período.")
        else:
            df_altas_plot = ranking_altas.copy()
            df_altas_plot = df_altas_plot.sort_values(
                "variacao_percentual",
                ascending=True
            )

            fig_altas, ax_altas = plt.subplots(
                figsize=(8, 5)
            )

            barras = ax_altas.barh(
                df_altas_plot["produto"],
                df_altas_plot["variacao_percentual"],
                facecolor="white",
                edgecolor="black",
                linewidth=1.2
            )

            for barra, valor in zip(
                barras,
                df_altas_plot["variacao_percentual"]
            ):
                ax_altas.text(
                    barra.get_width() + 0.5,
                    barra.get_y() + barra.get_height() / 2,
                    f"{valor:.2f}%",
                    va="center",
                    ha="left",
                    fontsize=9,
                    fontweight="bold"
                )

            ax_altas.set_title(
                "Maiores altas no período"
            )
            ax_altas.set_xlabel(
                "Variação percentual (%)"
            )
            ax_altas.set_ylabel("Produto")

            aplicar_estilo_impressao(
                ax_altas
            )
            ax_altas.grid(False)
            ax_altas.tick_params(
                axis="y",
                labelsize=8
            )
            plt.setp(
                ax_altas.get_yticklabels(),
                rotation=10,
                ha="right",
                va="center",
                rotation_mode="anchor"
            )

            fig_altas.subplots_adjust(
                left=0.38,
                right=0.94,
                top=0.88,
                bottom=0.16
            )
            st.pyplot(fig_altas)
            plt.close(fig_altas)

    with col_quedas:
        st.markdown("### 📉 Maiores quedas")

        if ranking_quedas.empty:
            st.info("Nenhum produto com queda no período.")
        else:
            df_quedas_plot = ranking_quedas.copy()
            df_quedas_plot = df_quedas_plot.sort_values(
                "variacao_percentual",
                ascending=True
            )

            fig_quedas, ax_quedas = plt.subplots(
                figsize=(8, 5)
            )

            barras = ax_quedas.barh(
                df_quedas_plot["produto"],
                df_quedas_plot["variacao_percentual"],
                facecolor="white",
                edgecolor="black",
                linewidth=1.2
            )

            for barra, valor in zip(
                barras,
                df_quedas_plot["variacao_percentual"]
            ):
                ax_quedas.text(
                    valor - 0.5,
                    barra.get_y() + barra.get_height() / 2,
                    f"{valor:.2f}%",
                    va="center",
                    ha="right",
                    fontsize=9,
                    fontweight="bold"
                )

            ax_quedas.set_title(
                "Maiores quedas no período"
            )
            ax_quedas.set_xlabel(
                "Variação percentual (%)"
            )
            ax_quedas.set_ylabel("Produto")

            aplicar_estilo_impressao(
                ax_quedas
            )
            ax_quedas.grid(False)
            ax_quedas.tick_params(
                axis="y",
                labelsize=8
            )
            plt.setp(
                ax_quedas.get_yticklabels(),
                rotation=10,
                ha="right",
                va="center",
                rotation_mode="anchor"
            )

            fig_quedas.subplots_adjust(
                left=0.38,
                right=0.94,
                top=0.88,
                bottom=0.16
            )
            st.pyplot(fig_quedas)
            plt.close(fig_quedas)

    # ================= HISTÓRICO POR PRODUTO =================
    st.divider()
    st.subheader("📉 Histórico de preço por produto")

    if produto_sel == "Todos":
        st.info("Selecione um produto específico no filtro acima para visualizar o histórico.")
    else:
        df_produto = df_periodo[
            df_periodo["produto"] == produto_sel
        ].copy()

        df_produto = df_produto.sort_values("data")

        if df_produto.empty:
            st.warning("Não há dados para o produto selecionado.")
        else:
            grafico = df_produto[
                ["data", "preco_medio"]
            ].copy()

            grafico["data"] = pd.to_datetime(
                grafico["data"],
                errors="coerce"
            )

            grafico = grafico.dropna(
                subset=["data", "preco_medio"]
            ).sort_values("data")

            fig_hist, ax_hist = plt.subplots(
                figsize=(9, 4.5)
            )

            marcador, estilo_linha = obter_estilo_linha(0)

            ax_hist.plot(
                grafico["data"],
                grafico["preco_medio"],
                color="black",
                linestyle=estilo_linha,
                marker=marcador,
                linewidth=2,
                markersize=7,
                markerfacecolor="white",
                markeredgecolor="black",
                markeredgewidth=1.2
            )

            ax_hist.set_title(
                f"Histórico de preço - {produto_sel}"
            )
            ax_hist.set_xlabel("Data")
            ax_hist.set_ylabel("Preço médio (R$)")

            aplicar_estilo_impressao(
                ax_hist
            )

            fig_hist.autofmt_xdate()
            fig_hist.tight_layout()

            st.pyplot(fig_hist)
            plt.close(fig_hist)

            menor = df_produto["preco_medio"].min()
            maior = df_produto["preco_medio"].max()
            media = df_produto["preco_medio"].mean()
            amplitude = maior - menor

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("Menor preço", formatar_moeda(menor))
            c2.metric("Maior preço", formatar_moeda(maior))
            c3.metric("Média", formatar_moeda(media))
            c4.metric("Amplitude", formatar_moeda(amplitude))

            st.dataframe(
                df_produto[
                    [
                        "data",
                        "classe",
                        "produto",
                        "unidade",
                        "kg",
                        "preco_min",
                        "preco_max",
                        "preco_medio",
                        "valor_kg"
                    ]
                ].assign(
                    data=lambda x: x["data"].dt.strftime("%d/%m/%Y")
                ),
                use_container_width=True
            )

    # ================= MÉDIA MENSAL =================
    st.divider()
    st.subheader("📅 Média mensal dos preços")

    df_mensal = df_periodo.copy()

    df_mensal["mes_ano"] = df_mensal["data"].dt.strftime("%m/%Y")

    media_mensal = (
        df_mensal
        .groupby(["mes_ano", "classe", "produto", "unidade"], as_index=False)
        .agg(
            kg=("kg", "mean"),
            preco_min=("preco_min", "mean"),
            preco_max=("preco_max", "mean"),
            preco_medio=("preco_medio", "mean"),
            valor_kg=("valor_kg", "mean"),
            qtd_cotacoes=("preco_medio", "count")
        )
    )

    media_mensal = ordenar_classes_relatorio(
        media_mensal,
        coluna_classe="classe",
        coluna_produto="produto",
        coluna_mes="mes_ano"
    )

    media_mensal_tabela = media_mensal.copy()

    media_mensal_tabela["kg"] = media_mensal_tabela["kg"].apply(
        lambda x: f"{float(x):.0f}" if pd.notnull(x) else ""
    )

    media_mensal_tabela["preco_min"] = media_mensal_tabela["preco_min"].apply(formatar_moeda)
    media_mensal_tabela["preco_max"] = media_mensal_tabela["preco_max"].apply(formatar_moeda)
    media_mensal_tabela["preco_medio"] = media_mensal_tabela["preco_medio"].apply(formatar_moeda)
    media_mensal_tabela["valor_kg"] = media_mensal_tabela["valor_kg"].apply(formatar_moeda)

    media_mensal_tabela = media_mensal_tabela.rename(columns={
        "mes_ano": "Mês-Ano",
        "classe": "Classe",
        "produto": "Produto",
        "unidade": "Unidade",
        "kg": "Kg",
        "preco_min": "Preço Mín",
        "preco_max": "Preço Máx",
        "preco_medio": "Preço Médio",
        "valor_kg": "Valor/Kg",
        "qtd_cotacoes": "Qtd. cotações"
    })

    colunas_media_mensal = [
        "Mês-Ano",
        "Classe",
        "Produto",
        "Unidade",
        "Kg",
        "Preço Mín",
        "Preço Máx",
        "Preço Médio",
        "Valor/Kg",
        "Qtd. cotações"
    ]

    media_mensal_tabela = media_mensal_tabela[colunas_media_mensal]

    st.dataframe(media_mensal_tabela, use_container_width=True)

    # ================= VOLUME MENSAL ESTIMADO =================
    st.divider()
    st.subheader("📦 Volume mensal estimado e valor comercializado")

    st.caption(
        "Este cálculo parte do volume do mesmo mês do ano anterior, aplica o ajuste geral "
        "do mês definido por você e, depois, faz uma correção pelo preço/kg médio. "
        "Os preços não são alterados; eles apenas orientam a estimativa do volume."
    )

    volume_mensal = pd.DataFrame()
    resumo_volume_classe = pd.DataFrame()
    resumo_volume_geral = pd.DataFrame()

    col_config1, col_config2, col_config3 = st.columns(3)

    with col_config1:
        kg_por_caminhao = st.number_input(
            "Kg por caminhão",
            min_value=1000,
            max_value=50000,
            value=15000,
            step=500,
            key="volume_kg_por_caminhao"
        )

    with col_config2:
        sensibilidade_preco = st.number_input(
            "Sensibilidade ao preço",
            min_value=0.0001,
            max_value=0.5000,
            value=0.0100,
            step=0.0001,
            format="%.4f",
            key="volume_sensibilidade_preco"
        )

    with col_config3:
        ajuste_volume_mensal_percentual = st.number_input(
            "Ajuste mensal do volume (%)",
            min_value=-80.0,
            max_value=150.0,
            value=0.0,
            step=1.0,
            key="volume_ajuste_volume_mensal_percentual"
        )

    meses_volume = media_mensal["mes_ano"].dropna().unique().tolist()

    try:
        volume_mensal, resumo_volume_classe, resumo_volume_geral, avisos_volume = gerar_volume_mensal_estimado_analise(
            supabase=supabase,
            df_cotacoes=df,
            meses_ano_atuais=meses_volume,
            classe_sel=classe_sel,
            kg_por_caminhao=kg_por_caminhao,
            sensibilidade_preco=sensibilidade_preco,
            ajuste_volume_mensal_percentual=ajuste_volume_mensal_percentual
        )

        if avisos_volume:
            with st.expander("Avisos do cálculo de volume"):
                for aviso in avisos_volume:
                    st.warning(aviso)

        if volume_mensal.empty:
            st.warning(
                "Não foi possível gerar o cálculo de volume mensal para os filtros selecionados. "
                "Confira se existem volumes do mesmo mês do ano anterior e cotações dos dois anos."
            )
        else:
            total_volume = resumo_volume_geral.iloc[0]["Volume total estimado (kg)"]
            total_caminhoes = resumo_volume_geral.iloc[0]["Caminhões estimados"]
            total_valor = resumo_volume_geral.iloc[0]["Valor comercializado estimado"]
            crescimento_valor = resumo_volume_geral.iloc[0]["Crescimento valor (%)"]
            variacao_volume = resumo_volume_geral.iloc[0]["Variação volume (%)"]

            v1, v2, v3, v4, v5 = st.columns(5)

            v1.metric("Volume estimado", f"{total_volume:,.0f} kg".replace(",", "."))
            v2.metric("Variação volume", formatar_percentual(variacao_volume))
            v3.metric("Caminhões", formatar_numero(total_caminhoes))
            v4.metric("Valor comercializado", formatar_moeda(total_valor))
            v5.metric("Crescimento em valor", formatar_percentual(crescimento_valor))

            colunas_volume_tela = [
                "Mês-Ano",
                "Classe",
                "Produto",
                "Quantidade ano anterior (kg)",
                "Quantidade (kg)",
                "Variação volume (%)",
                "Porcentagem (%)",
                "Caminhões",
                "Preço/kg ano anterior",
                "Preço/kg médio",
                "Variação preço (%)",
                "Valor comercializado",
                "Observação"
            ]

            st.markdown("#### Tabela de volume mensal")
            st.dataframe(
                formatar_volume_para_tela(volume_mensal[colunas_volume_tela]),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("#### Confirmar volume no banco de dados")

            volume_confirmado_pdf = volume_mensal_esta_confirmado(volume_mensal)

            if volume_confirmado_pdf:
                st.success(
                    "Este volume mensal já está confirmado no banco de dados. "
                    "Ele pode ser usado no Relatório Analítico em PDF."
                )
            else:
                st.caption(
                    "Ao confirmar, os volumes calculados serão salvos como volume oficial do mês atual. "
                    "Depois disso, quando esse mesmo mês for analisado novamente, o sistema usará o volume salvo "
                    "e não recalculará pelo ano anterior. Mesmo antes da confirmação, estes dados podem ser usados "
                    "no Relatório Analítico em PDF como prévia calculada."
                )

                if st.button(
                    "✅ Confirmar volumes calculados como atuais",
                    type="primary",
                    key="btn_confirmar_volume_calculado_banco"
                ):
                    try:
                        qtd_registros, meses_salvos = salvar_volume_mensal_confirmado(
                            supabase=supabase,
                            volume_mensal=volume_mensal,
                            classe_sel=classe_sel
                        )

                        st.success(
                            f"Volumes confirmados com sucesso: {qtd_registros} registro(s) salvo(s) "
                            f"para {', '.join(meses_salvos)}."
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao confirmar volumes no banco de dados: {e}")

            st.markdown("#### Total por classe")
            resumo_classe_tela = resumo_volume_classe.copy()

            for coluna in [
                "Quantidade ano anterior (kg)",
                "Quantidade (kg)",
                "Caminhões",
                "Variação volume (%)",
                "Crescimento valor (%)"
            ]:
                if coluna in resumo_classe_tela.columns:
                    resumo_classe_tela[coluna] = resumo_classe_tela[coluna].apply(formatar_numero)

            for coluna in ["Valor ano anterior", "Valor comercializado"]:
                if coluna in resumo_classe_tela.columns:
                    resumo_classe_tela[coluna] = resumo_classe_tela[coluna].apply(formatar_moeda)

            st.dataframe(
                resumo_classe_tela,
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:
        st.warning(f"Não foi possível gerar o cálculo de volume mensal: {e}")

    #=================================================================

        # ================= RELATÓRIO INDIVIDUAL DO PRODUTO =================
    st.divider()
    st.subheader("📄 Relatório individual do produto")

    if produto_sel == "Todos":
        st.info("Selecione um produto específico no filtro acima para gerar o relatório individual.")
    else:
        if st.button("📄 Gerar Relatório do Produto"):
            try:
                df_produto_relatorio = df_periodo[
                    df_periodo["produto"] == produto_sel
                ].copy()

                observacoes_produto = carregar_observacoes_produto_periodo(
                    supabase=supabase,
                    produto=produto_sel,
                    data_inicial=data_inicial,
                    data_final=data_final
                )

                nome_pdf_produto = (
                    f"relatorio_produto_{produto_sel.lower().replace(' ', '_')}_"
                    f"{datetime.now().strftime('%d-%m-%Y')}.pdf"
                )

                gerar_pdf_produto_analise(
                    df_produto=df_produto_relatorio,
                    observacoes=observacoes_produto,
                    nome_pdf=nome_pdf_produto,
                    produto_sel=produto_sel,
                    data_inicial=data_inicial,
                    data_final=data_final
                )

                with open(nome_pdf_produto, "rb") as f:
                    st.download_button(
                        "📥 Baixar Relatório do Produto",
                        f,
                        file_name=nome_pdf_produto,
                        mime="application/pdf"
                    )

                st.success("Relatório individual do produto gerado com sucesso.")

            except Exception as e:
                st.error(f"Erro ao gerar relatório individual do produto: {e}")
    #==========================================================================================

    # ================= EXPORTAÇÃO PDF =================
    st.divider()
    st.subheader("📄 Relatório analítico em PDF")

    if st.button("📄 Gerar Relatório Analítico em PDF"):
        try:
            # O PDF pode ser gerado tanto com volume confirmado quanto com volume em prévia.
            # Se ainda não estiver confirmado, o sistema apenas avisa, mas não bloqueia o relatório.
            if "volume_mensal" in locals() and volume_mensal is not None and not volume_mensal.empty:
                if not volume_mensal_esta_confirmado(volume_mensal):
                    st.info(
                        "O volume mensal usado no PDF ainda é uma prévia calculada com base no ano anterior. "
                        "Se quiser tornar esses valores oficiais, confirme os volumes no banco de dados depois."
                    )

            nome_pdf = f"relatorio_analitico_precos_{datetime.now().strftime('%d-%m-%Y')}.pdf"

            observacoes_gerais = carregar_observacoes_periodo(
                supabase=supabase,
                data_inicial=data_inicial,
                data_final=data_final,
                produto=None
            )

            gerar_pdf_analise_precos(
                comparativo=comparativo,
                alertas=alertas,
                media_mensal=media_mensal,
                df_periodo=df_periodo,
                observacoes=observacoes_gerais,
                nome_pdf=nome_pdf,
                data_inicial=data_inicial,
                data_final=data_final,
                classe_sel=classe_sel,
                produto_sel=produto_sel,
                volume_mensal=volume_mensal,
                resumo_volume_classe=resumo_volume_classe,
                resumo_volume_geral=resumo_volume_geral,
                ajuste_volume_mensal_percentual=ajuste_volume_mensal_percentual,
                sensibilidade_preco=sensibilidade_preco,
                kg_por_caminhao=kg_por_caminhao
            )

            with open(nome_pdf, "rb") as f:
                st.download_button(
                    "📥 Baixar Relatório Analítico em PDF",
                    f,
                    file_name=nome_pdf,
                    mime="application/pdf"
                )

            st.success("Relatório analítico gerado com sucesso.")

        except Exception as e:
            st.error(f"Erro ao gerar relatório analítico em PDF: {e}")

    # ================= EXPORTAÇÃO EXCEL =================
    st.divider()
    st.subheader("📥 Exportar análise em Excel")

    try:
        buffer = io.BytesIO()

        # Versões sem formatação textual para o Excel ficar mais útil
        comparativo_excel = comparativo.copy()

        comparativo_excel["data_inicial"] = pd.to_datetime(
            comparativo_excel["data_inicial"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        comparativo_excel["data_final"] = pd.to_datetime(
            comparativo_excel["data_final"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        comparativo_excel = comparativo_excel.rename(columns={
            "produto": "Produto",
            "classe": "Classe",
            "unidade": "Unidade",
            "kg": "Kg",
            "data_inicial": "Data inicial",
            "data_final": "Data final",
            "preco_medio_inicial": "Preço médio inicial",
            "preco_medio_final": "Preço médio final",
            "valor_kg_inicial": "Valor/kg inicial",
            "valor_kg_final": "Valor/kg final",
            "diferenca": "Diferença",
            "variacao_percentual": "Variação %",
            "status": "Status",
            "alerta": "Alerta"
        })

        media_mensal_excel = media_mensal.copy()

        media_mensal_excel = media_mensal_excel.rename(columns={
            "mes_ano": "Mês-Ano",
            "classe": "Classe",
            "produto": "Produto",
            "unidade": "Unidade",
            "kg": "Kg",
            "preco_min": "Preço Mín",
            "preco_max": "Preço Máx",
            "preco_medio": "Preço Médio",
            "valor_kg": "Valor/Kg",
            "qtd_cotacoes": "Qtd. cotações"
        })

        media_mensal_excel = media_mensal_excel[
            [
                "Mês-Ano",
                "Classe",
                "Produto",
                "Unidade",
                "Kg",
                "Preço Mín",
                "Preço Máx",
                "Preço Médio",
                "Valor/Kg",
                "Qtd. cotações"
            ]
        ]

        df_periodo_excel = df_periodo.copy()
        df_periodo_excel["data"] = df_periodo_excel["data"].dt.strftime("%d/%m/%Y")

        ranking_altas_excel = ranking_altas.copy()
        ranking_quedas_excel = ranking_quedas.copy()

        alertas_excel = alertas.copy()

        if not alertas_excel.empty:
            alertas_excel["data_inicial"] = pd.to_datetime(
                alertas_excel["data_inicial"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

            alertas_excel["data_final"] = pd.to_datetime(
                alertas_excel["data_final"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

            alertas_excel = alertas_excel.rename(columns={
                "produto": "Produto",
                "classe": "Classe",
                "unidade": "Unidade",
                "kg": "Kg",
                "data_inicial": "Data inicial",
                "data_final": "Data final",
                "preco_medio_inicial": "Preço médio inicial",
                "preco_medio_final": "Preço médio final",
                "valor_kg_inicial": "Valor/kg inicial",
                "valor_kg_final": "Valor/kg final",
                "diferenca": "Diferença",
                "variacao_percentual": "Variação %",
                "status": "Status",
                "alerta": "Alerta"
            })

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            comparativo_excel.to_excel(
                writer,
                sheet_name="Variacao_Produtos",
                index=False
            )

            media_mensal_excel.to_excel(
                writer,
                sheet_name="Media_Mensal",
                index=False
            )

            df_periodo_excel.to_excel(
                writer,
                sheet_name="Cotacoes_Periodo",
                index=False
            )

            ranking_altas_excel.to_excel(
                writer,
                sheet_name="Ranking_Altas",
                index=False
            )

            ranking_quedas_excel.to_excel(
                writer,
                sheet_name="Ranking_Quedas",
                index=False
            )

            alertas_excel.to_excel(
                writer,
                sheet_name="Alertas",
                index=False
            )

            if "volume_mensal" in locals() and not volume_mensal.empty:
                volume_mensal.to_excel(
                    writer,
                    sheet_name="Volume_Mensal",
                    index=False
                )

            if "resumo_volume_classe" in locals() and not resumo_volume_classe.empty:
                resumo_volume_classe.to_excel(
                    writer,
                    sheet_name="Volume_Classe",
                    index=False
                )

        buffer.seek(0)

        st.download_button(
            "📥 Baixar Excel da Análise de Preços",
            buffer,
            file_name=f"analise_precos_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Erro ao gerar Excel da análise: {e}")