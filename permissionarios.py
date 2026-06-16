import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from urllib.parse import quote
import unicodedata

from whatsapp_service import enviar_para_permissionario


TZ = ZoneInfo("America/Bahia")


def agora_brasil():
    return datetime.now(TZ)


def hoje_brasil():
    return agora_brasil().date()


def normalizar_whatsapp(numero):
    numero = str(numero).strip()
    numero = "".join([c for c in numero if c.isdigit()])

    if numero.startswith("55"):
        return numero

    return "55" + numero


def carregar_config(supabase):
    resp = (
        supabase
        .table("config_permissionarios")
        .select("*")
        .eq("id", 1)
        .limit(1)
        .execute()
    )

    dados = resp.data or []

    if dados:
        return dados[0]

    return {
        "id": 1,
        "hora_envio": "07:00:00",
        "hora_limite": "09:00:00",
        "mensagem": (
            "Bom dia! Por favor, informe os preços dos produtos "
            "solicitados para a cotação de hoje."
        ),
        "base_url": "",
        "ativo": False,
        "template_nome": "link_cotacao_diaria",
        "idioma": "pt_BR"
    }


def atualizar_config(
    supabase,
    hora_envio,
    hora_limite,
    mensagem,
    base_url,
    ativo,
    template_nome,
    idioma
):
    supabase.table("config_permissionarios").upsert({
        "id": 1,
        "hora_envio": str(hora_envio),
        "hora_limite": str(hora_limite),
        "mensagem": mensagem.strip(),
        "base_url": base_url.strip().rstrip("/"),
        "ativo": bool(ativo),
        "template_nome": template_nome.strip(),
        "idioma": idioma.strip(),
        "atualizado_em": agora_brasil().isoformat()
    }).execute()


def carregar_permissionarios(supabase):
    resp = supabase.table("permissionarios").select("*").order("nome").execute()
    return pd.DataFrame(resp.data or [])


def carregar_vinculos(supabase, permissionario_id):
    resp = supabase.table("permissionario_produtos")\
        .select("*")\
        .eq("permissionario_id", int(permissionario_id))\
        .eq("ativo", True)\
        .order("produto")\
        .execute()

    return pd.DataFrame(resp.data or [])


def salvar_vinculos(supabase, permissionario_id, produtos_df, produtos_selecionados):
    supabase.table("permissionario_produtos")\
        .delete()\
        .eq("permissionario_id", int(permissionario_id))\
        .execute()

    dados = []

    for produto in produtos_selecionados:
        linha = produtos_df[produtos_df["nome"] == produto]

        if not linha.empty:
            classe = str(linha.iloc[0].get("classe", ""))
        else:
            classe = ""

        dados.append({
            "permissionario_id": int(permissionario_id),
            "produto": str(produto).strip().upper(),
            "classe": classe,
            "ativo": True
        })

    if dados:
        supabase.table("permissionario_produtos").insert(dados).execute()


def gerar_link_permissionario(supabase, permissionario_id):
    config = carregar_config(supabase)

    base_url = str(config.get("base_url") or "").strip()
    if base_url == "":
        st.error("Cadastre a URL base do app antes de gerar o link.")
        return None, None

    data_hoje = hoje_brasil()
    hora_limite_txt = str(config.get("hora_limite") or "09:00:00")
    hora_limite = datetime.strptime(hora_limite_txt[:5], "%H:%M").time()

    valido_ate = datetime.combine(data_hoje, hora_limite, tzinfo=TZ)
    token = uuid.uuid4().hex

    supabase.table("links_permissionarios")\
        .delete()\
        .eq("permissionario_id", int(permissionario_id))\
        .eq("data", data_hoje.strftime("%Y-%m-%d"))\
        .execute()

    supabase.table("links_permissionarios").insert({
        "permissionario_id": int(permissionario_id),
        "data": data_hoje.strftime("%Y-%m-%d"),
        "token": token,
        "valido_ate": valido_ate.isoformat(),
        "usado": False
    }).execute()

    link = f"{base_url}?token={token}"
    return link, valido_ate


def montar_mensagem_whatsapp(nome, link, config):
    mensagem = str(config.get("mensagem") or "").strip()

    if mensagem == "":
        mensagem = "Bom dia! Por favor, informe os preços dos produtos solicitados para a cotação de hoje."

    texto = f"{mensagem}\n\nLink para preencher:\n{link}"
    return texto


def carregar_respostas_permissionarios(supabase, data_str):
    try:
        resp = supabase.table("respostas_permissionarios")\
            .select("*")\
            .eq("data", data_str)\
            .order("produto")\
            .execute()

        df = pd.DataFrame(resp.data or [])

        if not df.empty:
            df["produto"] = df["produto"].astype(str).str.strip().str.upper()
            df["preco"] = pd.to_numeric(df["preco"], errors="coerce")

        return df

    except Exception as e:
        st.error(f"Erro ao carregar respostas dos permissionários: {e}")
        return pd.DataFrame()
    
BUCKET_FOTOS = "fotos-produtos"

def limpar_nome_arquivo(texto):
    texto = str(texto).lower().strip()

    # remove acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")

    # troca caracteres especiais por _
    texto = "".join(
        c if c.isalnum() else "_"
        for c in texto
    )

    # remove underscores repetidos
    while "__" in texto:
        texto = texto.replace("__", "_")

    # remove _ do começo e do final
    texto = texto.strip("_")

    if texto == "":
        texto = "produto"

    return texto[:60]

def salvar_foto_permissionario(supabase, arquivo, permissionario_id, data_link, produto):
    nome_original = str(arquivo.name)
    extensao = nome_original.split(".")[-1].lower()

    if extensao not in ["jpg", "jpeg", "png", "webp"]:
        extensao = "jpg"

    produto_limpo = limpar_nome_arquivo(produto)

    nome_arquivo = (
        f"permissionarios/{data_link}/{permissionario_id}/"
        f"{produto_limpo}_{uuid.uuid4().hex}.{extensao}"
    )

    content_type = arquivo.type or f"image/{extensao}"

    supabase.storage.from_(BUCKET_FOTOS).upload(
        nome_arquivo,
        arquivo.getvalue(),
        {
            "content-type": content_type,
            "upsert": "true"
        }
    )

    url_foto = supabase.storage.from_(BUCKET_FOTOS).get_public_url(nome_arquivo)

    return url_foto, nome_arquivo


def carregar_fotos_permissionarios(supabase, data_str):
    try:
        resp = supabase.table("fotos_permissionarios")\
            .select("*")\
            .eq("data", data_str)\
            .order("produto")\
            .execute()

        df = pd.DataFrame(resp.data or [])

        if not df.empty:
            df["produto"] = df["produto"].astype(str).str.strip().str.upper()

        return df

    except Exception as e:
        st.error(f"Erro ao carregar fotos dos permissionários: {e}")
        return pd.DataFrame()


def tela_publica_permissionario(supabase, token):
    st.title("🧾 Envio de Preços")

    try:
        resp_link = supabase.table("links_permissionarios")\
            .select("*")\
            .eq("token", token)\
            .limit(1)\
            .execute()

        dados_link = resp_link.data or []

        if not dados_link:
            st.error("Link inválido.")
            return

        link = dados_link[0]

        valido_ate = pd.to_datetime(link["valido_ate"])
        agora = agora_brasil()

        if valido_ate.tzinfo is None:
            valido_ate = valido_ate.tz_localize("America/Bahia")

        if agora > valido_ate.to_pydatetime():
            st.error("Este link expirou. Entre em contato com a administração.")
            return

        permissionario_id = int(link["permissionario_id"])
        data_link = str(link["data"])

        resp_perm = supabase.table("permissionarios")\
            .select("*")\
            .eq("id", permissionario_id)\
            .limit(1)\
            .execute()

        dados_perm = resp_perm.data or []

        if not dados_perm:
            st.error("Permissionário não encontrado.")
            return

        permissionario = dados_perm[0]

        if not permissionario.get("ativo", True):
            st.error("Permissionário inativo.")
            return

        st.markdown(f"### Bom dia, {permissionario['nome']}!")
        st.info(f"Informe os preços dos produtos solicitados. Link válido até {valido_ate.strftime('%H:%M')}.")

        df_produtos = carregar_vinculos(supabase, permissionario_id)

        if df_produtos.empty:
            st.warning("Nenhum produto vinculado para este permissionário.")
            return

        with st.form("form_resposta_permissionario"):
            respostas = []
            fotos_para_salvar = []

            qtd_precos = int(permissionario.get("qtd_precos", 1) or 1)

            for _, row in df_produtos.iterrows():
                produto = str(row["produto"]).strip().upper()
                classe = str(row.get("classe", ""))

                st.markdown(f"### {produto}")

                cols = st.columns(3)

                for i in range(qtd_precos):
                    with cols[i % 3]:
                        preco = st.number_input(
                            f"Preço {i + 1}",
                            min_value=0.0,
                            step=0.10,
                            format="%.2f",
                            key=f"preco_publico_{produto}_{i}"
                        )

                        respostas.append({
                            "permissionario_id": permissionario_id,
                            "permissionario_nome": permissionario["nome"],
                            "data": data_link,
                            "produto": produto,
                            "classe": classe,
                            "numero_preco": i + 1,
                            "preco": preco
                        })

                fotos = st.file_uploader(
                    f"Fotos de {produto}",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key=f"fotos_publico_{produto}"
                )

                if fotos:
                    for foto in fotos:
                        fotos_para_salvar.append({
                            "produto": produto,
                            "classe": classe,
                            "arquivo": foto
                        })

                st.divider()

            enviar = st.form_submit_button("Enviar preços e fotos")

            if enviar:
                dados_validos = [r for r in respostas if float(r["preco"]) > 0]

                if not dados_validos and not fotos_para_salvar:
                    st.warning("Preencha pelo menos um preço ou envie uma foto antes de concluir.")
                    return

                # Apaga respostas antigas desse permissionário nesta data
                supabase.table("respostas_permissionarios")\
                    .delete()\
                    .eq("permissionario_id", permissionario_id)\
                    .eq("data", data_link)\
                    .execute()

                if dados_validos:
                    supabase.table("respostas_permissionarios").insert(dados_validos).execute()

                # Salva fotos, se houver
                if fotos_para_salvar:

                    # Apaga registros antigos de fotos desse permissionário nesta data
                    supabase.table("fotos_permissionarios")\
                        .delete()\
                        .eq("permissionario_id", permissionario_id)\
                        .eq("data", data_link)\
                        .execute()

                    dados_fotos = []

                    for item in fotos_para_salvar:
                        url_foto, nome_arquivo = salvar_foto_permissionario(
                            supabase,
                            item["arquivo"],
                            permissionario_id,
                            data_link,
                            item["produto"]
                        )

                        dados_fotos.append({
                            "permissionario_id": permissionario_id,
                            "permissionario_nome": permissionario["nome"],
                            "data": data_link,
                            "produto": item["produto"],
                            "classe": item["classe"],
                            "foto_url": url_foto,
                            "arquivo_nome": nome_arquivo
                        })

                    if dados_fotos:
                        supabase.table("fotos_permissionarios").insert(dados_fotos).execute()

                supabase.table("links_permissionarios")\
                    .update({"usado": True})\
                    .eq("token", token)\
                    .execute()

                st.success("Preços e fotos enviados com sucesso. Obrigada!")
    except Exception as e:
        st.error(f"Erro ao abrir link: {e}")

def tela_permissionarios_admin(supabase, carregar_produtos, corrigir_classe, registrar_acao):
    st.title("🧑‍🌾 Permissionários")

    abas = st.tabs([
        "Cadastro",
        "Produtos vinculados",
        "Links e mensagens",
        "Respostas"
    ])

    # ================= ABA 1 - CADASTRO =================
    with abas[0]:
        st.subheader("➕ Cadastrar Permissionário")

        nome = st.text_input("Nome do permissionário", key="perm_nome")
        whatsapp = st.text_input("WhatsApp", key="perm_whatsapp")

        qtd_precos = st.number_input(
            "Quantidade de preços que ele deve informar por produto",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            key="perm_qtd_precos"
        )

        if st.button("Cadastrar Permissionário"):
            if nome.strip() == "" or whatsapp.strip() == "":
                st.warning("Preencha nome e WhatsApp.")
            else:
                try:
                    supabase.table("permissionarios").insert({
                        "nome": nome.strip(),
                        "whatsapp": normalizar_whatsapp(whatsapp),
                        "qtd_precos": int(qtd_precos),
                        "ativo": True
                    }).execute()

                    registrar_acao(
                        "Cadastro de permissionário",
                        "Permissionários",
                        f"Permissionário cadastrado: {nome.strip()}"
                    )

                    st.success("Permissionário cadastrado com sucesso!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao cadastrar permissionário: {e}")

        st.divider()

        st.subheader("📋 Permissionários cadastrados")

        df_perm = carregar_permissionarios(supabase)

        if df_perm.empty:
            st.info("Nenhum permissionário cadastrado.")
        else:
            st.dataframe(df_perm, use_container_width=True)

            st.subheader("✏️ Editar / Ativar / Inativar")

            ids = df_perm["id"].tolist()
            id_sel = st.selectbox("Selecione", ids, key="perm_id_editar")

            dados = df_perm[df_perm["id"] == id_sel].iloc[0]

            novo_nome = st.text_input(
                "Nome",
                value=str(dados["nome"]),
                key="edit_perm_nome"
            )

            novo_whatsapp = st.text_input(
                "WhatsApp",
                value=str(dados["whatsapp"]),
                key="edit_perm_whatsapp"
            )

            qtd_precos_edit = st.number_input(
                "Quantidade de preços por produto",
                min_value=1,
                max_value=10,
                value=int(dados.get("qtd_precos", 1) or 1),
                step=1,
                key="edit_perm_qtd_precos"
            )

            ativo = st.checkbox(
                "Ativo",
                value=bool(dados.get("ativo", True)),
                key="edit_perm_ativo"
            )                  

            if st.button("Atualizar Permissionário"):
                try:
                    supabase.table("permissionarios").update({
                        "nome": novo_nome.strip(),
                        "whatsapp": normalizar_whatsapp(novo_whatsapp),
                        "qtd_precos": int(qtd_precos_edit),
                        "ativo": ativo
                    }).eq("id", int(id_sel)).execute()

                    registrar_acao(
                        "Atualização de permissionário",
                        "Permissionários",
                        f"Permissionário atualizado: {novo_nome.strip()}"
                    )

                    st.success("Permissionário atualizado!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao atualizar permissionário: {e}")

    # ================= ABA 2 - PRODUTOS =================
    with abas[1]:
        st.subheader("📦 Vincular produtos ao permissionário")

        df_perm = carregar_permissionarios(supabase)

        if df_perm.empty:
            st.info("Cadastre um permissionário primeiro.")
        else:
            nomes = df_perm["nome"].tolist()
            nome_sel = st.selectbox("Permissionário", nomes, key="perm_prod_nome")
            perm = df_perm[df_perm["nome"] == nome_sel].iloc[0]
            perm_id = int(perm["id"])

            produtos = carregar_produtos()

            if produtos.empty:
                st.warning("Nenhum produto cadastrado no sistema.")
            else:
                produtos["nome"] = produtos["nome"].astype(str).str.strip().str.upper()
                produtos["classe"] = produtos["classe"].apply(corrigir_classe)
                produtos = produtos.sort_values(["classe", "nome"])

                vinculos = carregar_vinculos(supabase, perm_id)

                produtos_atuais = []
                if not vinculos.empty:
                    produtos_atuais = vinculos["produto"].astype(str).str.strip().str.upper().tolist()

                selecionados = st.multiselect(
                    "Produtos",
                    produtos["nome"].tolist(),
                    default=[p for p in produtos_atuais if p in produtos["nome"].tolist()],
                    key="multi_prod_permissionario"
                )

                if st.button("Salvar produtos vinculados"):
                    try:
                        salvar_vinculos(supabase, perm_id, produtos, selecionados)

                        registrar_acao(
                            "Vínculo de produtos",
                            "Permissionários",
                            f"Produtos vinculados para {nome_sel}: {len(selecionados)}"
                        )

                        st.success("Produtos vinculados com sucesso!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao salvar vínculos: {e}")

    # ================= ABA 3 - LINKS =================
    with abas[2]:
        st.subheader("⚙️ Configurações de envio automático")

        config = carregar_config(supabase)

        hora_envio_txt = str(
            config.get("hora_envio") or "07:00"
        )[:5]

        hora_limite_txt = str(
            config.get("hora_limite") or "09:00"
        )[:5]

        ativo_automacao = st.toggle(
            "Ativar envio automático",
            value=bool(config.get("ativo", False)),
            key="cfg_ativo_whatsapp"
        )

        col_hora_envio, col_hora_limite = st.columns(2)

        with col_hora_envio:
            hora_envio = st.time_input(
                "Horário de envio da mensagem",
                value=datetime.strptime(
                    hora_envio_txt,
                    "%H:%M"
                ).time(),
                key="cfg_hora_envio"
            )

        with col_hora_limite:
            hora_limite = st.time_input(
                "Horário limite do link",
                value=datetime.strptime(
                    hora_limite_txt,
                    "%H:%M"
                ).time(),
                key="cfg_hora_limite"
            )

        if hora_limite <= hora_envio:
            st.warning(
                "O horário limite deve ser posterior "
                "ao horário de envio."
            )

        mensagem = st.text_area(
            "Mensagem enviada junto com o link",
            value=str(config.get("mensagem") or ""),
            height=120,
            key="cfg_mensagem_perm"
        )

        base_url = st.text_input(
            "URL do sistema publicado",
            value=str(config.get("base_url") or ""),
            help=(
                "Use o endereço completo do sistema online. "
                "Exemplo: https://seu-sistema.onrender.com"
            ),
            key="cfg_base_url"
        )

        col_template, col_idioma = st.columns(2)

        with col_template:
            template_nome = st.text_input(
                "Nome do modelo aprovado na Meta",
                value=str(
                    config.get("template_nome")
                    or "link_cotacao_diaria"
                ),
                key="cfg_template_nome"
            )

        with col_idioma:
            idioma = st.text_input(
                "Idioma do modelo",
                value=str(
                    config.get("idioma")
                    or "pt_BR"
                ),
                key="cfg_template_idioma"
            )

        if st.button(
            "Salvar configurações",
            type="primary"
        ):
            if hora_limite <= hora_envio:
                st.error(
                    "Corrija os horários antes de salvar."
                )
            elif not base_url.strip():
                st.error(
                    "Informe a URL do sistema publicado."
                )
            elif not template_nome.strip():
                st.error(
                    "Informe o nome do modelo aprovado."
                )
            else:
                try:
                    atualizar_config(
                        supabase=supabase,
                        hora_envio=hora_envio,
                        hora_limite=hora_limite,
                        mensagem=mensagem,
                        base_url=base_url,
                        ativo=ativo_automacao,
                        template_nome=template_nome,
                        idioma=idioma
                    )

                    registrar_acao(
                        "Configuração de permissionários",
                        "Permissionários",
                        (
                            f"Envio automático: "
                            f"{'ativado' if ativo_automacao else 'desativado'} | "
                            f"Horário: {hora_envio} | "
                            f"Limite: {hora_limite}"
                        )
                    )

                    st.success(
                        "Configurações salvas com sucesso."
                    )
                    st.rerun()

                except Exception as e:
                    st.error(
                        f"Erro ao salvar configurações: {e}"
                    )

        st.divider()
        st.subheader("🧪 Testar envio pelo WhatsApp")

        st.caption(
            "Salve a configuração antes do teste. "
            "O teste envia uma mensagem real para apenas "
            "um permissionário."
        )

        df_perm = carregar_permissionarios(supabase)

        if df_perm.empty:
            st.info(
                "Nenhum permissionário cadastrado."
            )
        else:
            df_ativos = df_perm[
                df_perm["ativo"] == True
            ].copy()

            if df_ativos.empty:
                st.info(
                    "Nenhum permissionário ativo."
                )
            else:
                nome_teste = st.selectbox(
                    "Permissionário para o teste",
                    df_ativos["nome"].tolist(),
                    key="perm_teste_whatsapp"
                )

                perm_teste = (
                    df_ativos[
                        df_ativos["nome"] == nome_teste
                    ]
                    .iloc[0]
                    .to_dict()
                )

                st.write(
                    "Número que receberá o teste:",
                    perm_teste.get("whatsapp", "")
                )

                if st.button(
                    "Enviar mensagem de teste",
                    key="btn_teste_whatsapp"
                ):
                    with st.spinner(
                        "Enviando mensagem de teste..."
                    ):
                        resultado = enviar_para_permissionario(
                            supabase=supabase,
                            permissionario=perm_teste,
                            config=carregar_config(supabase),
                            registrar=False,
                            impedir_duplicado=False
                        )

                    if resultado.get("ok"):
                        st.success(
                            "Mensagem de teste enviada com sucesso."
                        )
                        st.write(
                            "Link enviado:",
                            resultado.get("link", "")
                        )
                    else:
                        st.error(
                            "Não foi possível enviar a mensagem."
                        )
                        st.code(
                            str(
                                resultado.get(
                                    "erro",
                                    resultado
                                )
                            )
                        )

        st.divider()
        st.subheader("🔗 Gerar link manual de hoje")

        if df_perm.empty:
            st.info(
                "Nenhum permissionário cadastrado."
            )
        else:
            nome_sel = st.selectbox(
                "Permissionário para gerar link",
                df_perm["nome"].tolist(),
                key="perm_link_nome"
            )

            perm = (
                df_perm[
                    df_perm["nome"] == nome_sel
                ]
                .iloc[0]
            )

            perm_id = int(perm["id"])

            if st.button("Gerar link"):
                link, valido_ate = gerar_link_permissionario(
                    supabase,
                    perm_id
                )

                if link:
                    config = carregar_config(supabase)
                    texto = montar_mensagem_whatsapp(
                        nome_sel,
                        link,
                        config
                    )

                    whatsapp = normalizar_whatsapp(
                        perm["whatsapp"]
                    )

                    wa_link = (
                        f"https://wa.me/{whatsapp}"
                        f"?text={quote(texto, safe='')}"
                    )

                    st.success(
                        "Link gerado com sucesso."
                    )
                    st.code(link)

                    st.markdown(
                        f"[Abrir mensagem no WhatsApp]({wa_link})"
                    )

                    registrar_acao(
                        "Link de permissionário gerado",
                        "Permissionários",
                        (
                            f"Link gerado para {nome_sel}, "
                            f"válido até "
                            f"{valido_ate.strftime('%H:%M')}"
                        )
                    )

    # ================= ABA 4 - RESPOSTAS =================
    with abas[3]:
        st.subheader("📊 Respostas recebidas")

        data_ref = st.date_input(
            "Data das respostas",
            value=hoje_brasil(),
            key="data_respostas_perm"
        )

        data_str = data_ref.strftime("%Y-%m-%d")

        df_resp = carregar_respostas_permissionarios(supabase, data_str)

        if df_resp.empty:
            st.info("Nenhuma resposta registrada para essa data.")
        else:
            df_mostrar = df_resp.copy()
            df_mostrar["preco"] = df_mostrar["preco"].apply(
                lambda x: f"{float(x):.2f}".replace(".", ",") if pd.notnull(x) else ""
            )

            st.dataframe(df_mostrar, use_container_width=True)

def tela_respostas_permissionarios(supabase):
    st.title("📊 Respostas dos Permissionários")

    # ================= FILTROS =================
    st.subheader("🔎 Filtros")

    col_data, col_perm, col_prod = st.columns(3)

    with col_data:
        data_ref = st.date_input(
            "Data das respostas",
            value=hoje_brasil(),
            key="data_respostas_permissionarios_geral"
        )

    data_str = data_ref.strftime("%Y-%m-%d")

    # ================= CARREGAR DADOS =================
    df_resp = carregar_respostas_permissionarios(supabase, data_str)
    df_fotos = carregar_fotos_permissionarios(supabase, data_str)

    # Monta lista de permissionários
    permissionarios_lista = []

    if not df_resp.empty and "permissionario_nome" in df_resp.columns:
        permissionarios_lista += df_resp["permissionario_nome"].dropna().astype(str).tolist()

    if not df_fotos.empty and "permissionario_nome" in df_fotos.columns:
        permissionarios_lista += df_fotos["permissionario_nome"].dropna().astype(str).tolist()

    permissionarios_lista = sorted(list(set(permissionarios_lista)))

    # Monta lista de produtos
    produtos_lista = []

    if not df_resp.empty:
        produtos_lista += df_resp["produto"].dropna().astype(str).str.upper().tolist()

    if not df_fotos.empty:
        produtos_lista += df_fotos["produto"].dropna().astype(str).str.upper().tolist()

    produtos_lista = sorted(list(set(produtos_lista)))

    with col_perm:
        filtro_permissionario = st.selectbox(
            "Permissionário",
            ["Todos"] + permissionarios_lista,
            key="filtro_resp_permissionario"
        )

    with col_prod:
        filtro_produto = st.selectbox(
            "Produto",
            ["Todos"] + produtos_lista,
            key="filtro_resp_produto"
        )

    if df_resp.empty and df_fotos.empty:
        st.warning(
            f"Nenhuma resposta registrada para {data_ref.strftime('%d/%m/%Y')}."
        )
        return

    # ================= PREÇOS =================
    st.subheader("💰 Preços enviados")

    if df_resp.empty:
        st.info("Nenhum preço enviado para essa data.")
    else:
        df_precos = df_resp.copy()

        df_precos["produto"] = df_precos["produto"].astype(str).str.strip().str.upper()

        if filtro_permissionario != "Todos":
            df_precos = df_precos[
                df_precos["permissionario_nome"] == filtro_permissionario
            ]

        if filtro_produto != "Todos":
            df_precos = df_precos[
                df_precos["produto"] == filtro_produto
            ]

        if df_precos.empty:
            st.warning("Nenhum preço encontrado com os filtros selecionados.")
        else:
            if "numero_preco" in df_precos.columns:
                df_precos = df_precos.sort_values(
                    ["permissionario_nome", "produto", "numero_preco"]
                )
            else:
                df_precos = df_precos.sort_values(
                    ["permissionario_nome", "produto"]
                )

            df_mostrar = df_precos.copy()

            if "preco" in df_mostrar.columns:
                df_mostrar["preco"] = df_mostrar["preco"].apply(
                    lambda x: f"{float(x):.2f}".replace(".", ",") if pd.notnull(x) else ""
                )

            if "enviado_em" in df_mostrar.columns:
                df_mostrar["enviado_em"] = pd.to_datetime(
                    df_mostrar["enviado_em"],
                    errors="coerce"
                ).dt.strftime("%d/%m/%Y %H:%M")

            colunas_exibir = [
                "permissionario_nome",
                "produto",
                "classe",
                "numero_preco",
                "preco",
                "enviado_em"
            ]

            colunas_existentes = [c for c in colunas_exibir if c in df_mostrar.columns]

            st.dataframe(
                df_mostrar[colunas_existentes],
                use_container_width=True
            )

    # ================= FOTOS =================
    st.subheader("📷 Fotos enviadas")

    if df_fotos.empty:
        st.info("Nenhuma foto enviada para essa data.")
    else:
        df_img = df_fotos.copy()

        df_img["produto"] = df_img["produto"].astype(str).str.strip().str.upper()

        if filtro_permissionario != "Todos":
            df_img = df_img[
                df_img["permissionario_nome"] == filtro_permissionario
            ]

        if filtro_produto != "Todos":
            df_img = df_img[
                df_img["produto"] == filtro_produto
            ]

        if df_img.empty:
            st.warning("Nenhuma foto encontrada com os filtros selecionados.")
        else:
            for _, row in df_img.iterrows():
                with st.container():
                    st.markdown(f"### 📦 {row.get('produto', '')}")
                    st.caption(
                        f"Permissionário: {row.get('permissionario_nome', '')} | "
                        f"Classe: {row.get('classe', '')}"
                    )

                    st.image(
                        row.get("foto_url", ""),
                        width=350
                    )

                    st.markdown(
                        f"[Abrir foto em nova aba]({row.get('foto_url', '')})"
                    )

                    st.divider()