import pandas as pd
import streamlit as st

from cotacao_repository import salvar_cotacoes_com_protecao
from cotacao_utils import (
    calcular_precos_validos,
    calcular_resumo_precos,
    calcular_variacao_percentual,
    montar_registro_cotacao,
    montar_registros_cotacoes,
    obter_sugestoes_cotacao,
    ordenar_produtos_para_cotacao,
    preparar_ultimas_cotacoes
)
from dados_utils import (
    carregar_produtos,
    carregar_todas_cotacoes,
    registrar_acao
)
from permissionarios import carregar_respostas_permissionarios


def tela_cotacao_dia(supabase):
    st.title("📊 Cotação do Dia")

    mensagem_cotacao_atual = st.session_state.get("msg_cotacao")

    if mensagem_cotacao_atual:
        tipo, texto = mensagem_cotacao_atual

        if tipo == "success":
            st.success(texto)
        else:
            st.error(texto)

        st.session_state.msg_cotacao = False

    if "confirmar_cotacao" not in st.session_state:
        st.session_state.confirmar_cotacao = False

    data = st.date_input(
        "Data",
        value=pd.to_datetime("today"),
        key="data_cotacao_dia"
    )

    data_str = data.strftime("%Y-%m-%d")
    respostas_permissionarios = carregar_respostas_permissionarios(supabase, data_str)

    if st.session_state.data_cotacao_atual != data_str:
        st.session_state.confirmar_cotacao = False
        st.session_state.data_cotacao_atual = data_str

    try:
        resp_data = (
            supabase
            .table("cotacoes")
            .select("id")
            .eq("data", data_str)
            .execute()
        )

        cotacao_ja_existe = bool(resp_data.data)

    except Exception as e:
        st.error(f"Erro ao verificar data da cotação: {e}")
        cotacao_ja_existe = False

    if cotacao_ja_existe:
        st.warning(
            f"⚠️ Já existe cotação cadastrada para {data.strftime('%d/%m/%Y')}. "
            "Se você confirmar, a cotação anterior dessa data será substituída."
        )

    try:
        produtos = ordenar_produtos_para_cotacao(
            carregar_produtos(supabase)
        )

    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        st.stop()

    if produtos.empty:
        st.warning("Cadastre produtos primeiro!")
        st.stop()

    try:
        df_ultimas = carregar_todas_cotacoes(supabase)
        df_ultimas = preparar_ultimas_cotacoes(df_ultimas)

    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        df_ultimas = pd.DataFrame()

    cotacoes = []

    def salvar_produto_cotacao_individual(
        produto_c,
        classe_c,
        unidade_c,
        kg_c,
        lista_precos,
        data_str_c,
        data_obj
    ):
        """
        Salva somente um produto na cotação da data selecionada.
        Se o produto já existir nessa data, ele é substituído.
        """

        if not lista_precos:
            st.session_state.msg_cotacao = (
                "error",
                f"Informe pelo menos um preço válido para salvar {produto_c}."
            )
            st.rerun()

        registro = montar_registro_cotacao(
            data_str=data_str_c,
            produto=produto_c,
            classe=classe_c,
            unidade=unidade_c,
            kg=kg_c,
            lista_precos=lista_precos,
            normalizar_kg_salvo=True
        )

        try:
            response = salvar_cotacoes_com_protecao(
                supabase,
                data_str_c,
                [registro],
                produto=produto_c
            )

            if response.data:
                st.session_state.msg_cotacao = (
                    "success",
                    f"{produto_c} salvo com sucesso para {data_obj.strftime('%d/%m/%Y')}."
                )

                registrar_acao(
                    supabase,
                    "Cotação salva por produto",
                    "Cotação do Dia",
                    f"Produto {produto_c} salvo individualmente para a data {data_obj.strftime('%d/%m/%Y')}"
                )

                st.cache_data.clear()
                st.rerun()

            st.session_state.msg_cotacao = (
                "error",
                f"Erro ao salvar {produto_c}."
            )
            st.rerun()

        except Exception as e:
            st.session_state.msg_cotacao = (
                "error",
                f"Erro ao salvar {produto_c}: {e}"
            )
            st.rerun()

    for _, row in produtos.iterrows():
        produto = str(row["nome"]).strip().upper()

        if not df_ultimas.empty:
            ultima = df_ultimas[df_ultimas["produto"] == produto]
        else:
            ultima = pd.DataFrame()

        col1, col2 = st.columns([1, 2])

        with col1:
            st.write(produto)

        with col2:
            key = f"precos_{produto}"
            sug_key = f"sugestoes_{produto}"

            if key not in st.session_state or sug_key not in st.session_state:
                if not ultima.empty:
                    sugestoes = obter_sugestoes_cotacao(ultima.iloc[0])

                    st.session_state[sug_key] = sugestoes
                    st.session_state[key] = [""] * len(sugestoes)

                else:
                    st.session_state[sug_key] = []
                    st.session_state[key] = []

            precos = st.session_state[key]
            sugestoes = st.session_state.get(sug_key, [])

            b1, b2 = st.columns(2)

            with b1:
                if st.button("➕ Adicionar", key=f"add_{produto}"):
                    precos.append("")
                    sugestoes.append(None)

            with b2:
                if precos and st.button("➖ Remover", key=f"rem_{produto}"):
                    precos.pop()

                    if sugestoes:
                        sugestoes.pop()

            cols = st.columns(3)

            for i in range(len(precos)):
                with cols[i % 3]:
                    placeholder = ""

                    if i < len(sugestoes) and sugestoes[i]:
                        placeholder = f"{float(sugestoes[i]):.2f}".replace(".", ",")

                    valor_digitado = st.text_input(
                        f"P{i+1}",
                        value=precos[i],
                        placeholder=placeholder,
                        key=f"{produto}_{i}_txt"
                    )

                    precos[i] = valor_digitado

            precos_validos = calcular_precos_validos(precos, sugestoes)

            if not respostas_permissionarios.empty:
                resp_produto = respostas_permissionarios[
                    respostas_permissionarios["produto"] == produto
                ]

                if not resp_produto.empty:
                    st.markdown("**Preços enviados por permissionários:**")

                    for _, r in resp_produto.iterrows():
                        nome_perm = str(r.get("permissionario_nome", ""))
                        preco_perm = float(r.get("preco", 0))

                        if preco_perm > 0:
                            numero_preco = r.get("numero_preco", "")

                            st.caption(
                                f"🧑‍🌾 {nome_perm} - Preço {numero_preco}: R$ {preco_perm:.2f}".replace(".", ",")
                            )

            pmin, pmax, preco_medio, valor_kg = calcular_resumo_precos(
                precos_validos,
                row["kg"]
            )

            st.caption(
                f"🔽 Mín: {pmin:.2f} | 🔼 Máx: {pmax:.2f} | 📊 Médio: {preco_medio:.2f} | ⚖️ Kg: {valor_kg:.2f}"
            )

            if not ultima.empty:
                valor_kg_anterior = float(ultima.iloc[0]["valor_kg"])

                if valor_kg_anterior > 0:
                    variacao = calcular_variacao_percentual(
                        valor_kg,
                        valor_kg_anterior
                    )

                    if abs(variacao) > 30:
                        st.warning(f"⚠️ Variação alta: {variacao:.1f}%")

        with col1:
            st.write("")

            if st.button(
                "Salvar",
                key=f"salvar_produto_{produto}"
            ):
                salvar_produto_cotacao_individual(
                    produto_c=produto,
                    classe_c=row["classe"],
                    unidade_c=row["unidade"],
                    kg_c=row["kg"],
                    lista_precos=precos_validos.copy(),
                    data_str_c=data_str,
                    data_obj=data
                )

        st.divider()

        cotacoes.append((
            produto,
            row["classe"],
            row["unidade"],
            row["kg"],
            pmin,
            pmax,
            precos_validos.copy()
        ))

    if not st.session_state.confirmar_cotacao:
        if st.button("💾 Salvar Cotação", key="btn_salvar_cotacao"):
            st.session_state.confirmar_cotacao = True
            st.rerun()

    else:
        if cotacao_ja_existe:
            st.warning(
                f"⚠️ Atenção: ao confirmar, a cotação anterior de "
                f"{data.strftime('%d/%m/%Y')} será apagada e substituída por esta."
            )
        else:
            st.warning("Deseja confirmar o salvamento desta cotação?")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✅ Confirmar", key="btn_confirmar_cotacao"):
                try:
                    dados_insert = montar_registros_cotacoes(
                        cotacoes,
                        data_str
                    )

                    if not dados_insert:
                        st.session_state.msg_cotacao = (
                            "error",
                            "Nenhum dado encontrado para salvar."
                        )

                    else:
                        response = salvar_cotacoes_com_protecao(
                            supabase,
                            data_str,
                            dados_insert
                        )

                        if response.data:
                            if cotacao_ja_existe:
                                st.session_state.msg_cotacao = (
                                    "success",
                                    "Cotação substituída com sucesso!"
                                )

                                registrar_acao(
                                    supabase,
                                    "Cotação substituída",
                                    "Cotação do Dia",
                                    f"Cotação substituída para a data {data.strftime('%d/%m/%Y')}"
                                )

                            else:
                                st.session_state.msg_cotacao = (
                                    "success",
                                    "Cotação salva com sucesso!"
                                )

                                registrar_acao(
                                    supabase,
                                    "Cotação salva",
                                    "Cotação do Dia",
                                    f"Cotação cadastrada para a data {data.strftime('%d/%m/%Y')}"
                                )

                            st.cache_data.clear()

                        else:
                            st.session_state.msg_cotacao = (
                                "error",
                                "Erro ao salvar cotação."
                            )

                except Exception as e:
                    st.session_state.msg_cotacao = (
                        "error",
                        f"Erro ao salvar: {e}"
                    )

                st.session_state.confirmar_cotacao = False
                st.rerun()

        with c2:
            if st.button("❌ Cancelar", key="btn_cancelar_cotacao"):
                st.session_state.confirmar_cotacao = False
                st.rerun()
