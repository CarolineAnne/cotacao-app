import streamlit as st
import uuid

from datetime import datetime, time
from zoneinfo import ZoneInfo

from utils import data_hoje_brasil, limpar_whatsapp


BASE_URL_APP = "http://localhost:8501"
# Quando o sistema estiver online, troque por:
# BASE_URL_APP = "https://cotacao-app-ghbu78rsvydesu7c5bjrra.streamlit.app"


def tela_configuracao_whatsapp(supabase):
    st.title("Configuração do WhatsApp")

    st.info(
        "Nesta tela você configura o envio automático do link de cotação "
        "para os permissionários cadastrados."
    )

    try:
        resposta = (
            supabase
            .table("config_whatsapp")
            .select("*")
            .eq("id", 1)
            .execute()
        )

        if resposta.data:
            config = resposta.data[0]

            ativo_atual = config.get("ativo", False)
            horario_atual = config.get("horario_envio", "08:00:00")
            hora_limite_atual = config.get("hora_limite", "09:00:00")
            template_atual = config.get("template_nome", "link_cotacao_diaria")
            idioma_atual = config.get("idioma", "pt_BR")
            mensagem_atual = config.get(
                "mensagem",
                "Bom dia! Por favor, informe os preços dos produtos solicitados para a cotação de hoje."
            )
            base_url_atual = config.get("base_url", "http://localhost:8501")

        else:
            ativo_atual = False
            horario_atual = "08:00:00"
            hora_limite_atual = "09:00:00"
            template_atual = "link_cotacao_diaria"
            idioma_atual = "pt_BR"
            mensagem_atual = "Bom dia! Por favor, informe os preços dos produtos solicitados para a cotação de hoje."
            base_url_atual = "http://localhost:8501"

    except Exception as e:
        st.error("Erro ao buscar configuração do WhatsApp.")
        st.exception(e)
        return

    def converter_horario(valor, padrao_hora, padrao_minuto):
        try:
            partes = str(valor).split(":")
            return time(int(partes[0]), int(partes[1]))
        except Exception:
            return time(padrao_hora, padrao_minuto)

    horario_formatado = converter_horario(horario_atual, 8, 0)
    hora_limite_formatada = converter_horario(hora_limite_atual, 9, 0)

    st.divider()
    st.subheader("Dados da automação")

    ativo = st.toggle(
        "Ativar envio automático",
        value=ativo_atual
    )

    col1, col2 = st.columns(2)

    with col1:
        horario_envio = st.time_input(
            "Horário de envio das mensagens",
            value=horario_formatado
        )

    with col2:
        hora_limite = st.time_input(
            "Horário de vencimento do link",
            value=hora_limite_formatada
        )

    mensagem = st.text_area(
        "Mensagem do WhatsApp",
        value=mensagem_atual,
        height=120,
        help="Essa mensagem será enviada dentro do template aprovado no WhatsApp."
    )

    base_url = st.text_input(
        "URL base do sistema",
        value=base_url_atual,
        help="Exemplo local: http://localhost:8501 | Exemplo online: https://seuapp.streamlit.app"
    )

    template_nome = st.text_input(
        "Nome do template aprovado no WhatsApp",
        value=template_atual
    )

    idioma = st.text_input(
        "Idioma do template",
        value=idioma_atual
    )

    st.divider()

    if hora_limite <= horario_envio:
        st.warning(
            "Atenção: o horário de vencimento está igual ou anterior ao horário de envio. "
            "O ideal é o link vencer depois do envio."
        )

    st.warning(
        "A automação só enviará mensagens quando o arquivo automacao_whatsapp.py "
        "estiver rodando no computador ou servidor."
    )

    if st.button("Salvar configuração", type="primary"):
        try:
            dados = {
                "id": 1,
                "ativo": ativo,
                "horario_envio": horario_envio.strftime("%H:%M:%S"),
                "hora_limite": hora_limite.strftime("%H:%M:%S"),
                "mensagem": mensagem.strip(),
                "base_url": base_url.strip().rstrip("/"),
                "template_nome": template_nome.strip(),
                "idioma": idioma.strip(),
                "atualizado_em": datetime.now().isoformat()
            }

            (
                supabase
                .table("config_whatsapp")
                .upsert(dados)
                .execute()
            )

            st.success("Configuração do WhatsApp salva com sucesso.")

        except Exception as e:
            st.error("Erro ao salvar configuração do WhatsApp.")
            st.exception(e)


def buscar_permissionarios_ativos(supabase):
    try:
        resposta = (
            supabase
            .table("permissionarios")
            .select("id, nome, whatsapp, ativo")
            .eq("ativo", True)
            .execute()
        )

        return resposta.data if resposta.data else []

    except Exception as e:
        st.error("Erro ao buscar permissionários ativos.")
        st.exception(e)
        return []


def gerar_link_cotacao_permissionario(supabase, permissionario_id):
    data_hoje = data_hoje_brasil().isoformat()

    agora = datetime.now(ZoneInfo("America/Bahia"))
    valido_ate = agora.replace(hour=23, minute=59, second=59, microsecond=0)

    resp_link = (
        supabase
        .table("links_permissionarios")
        .select("*")
        .eq("permissionario_id", permissionario_id)
        .eq("data", data_hoje)
        .limit(1)
        .execute()
    )

    if resp_link.data:
        token = resp_link.data[0]["token"]

    else:
        token = uuid.uuid4().hex

        supabase.table("links_permissionarios").insert({
            "permissionario_id": permissionario_id,
            "token": token,
            "data": data_hoje,
            "valido_ate": valido_ate.isoformat(),
            "usado": False
        }).execute()

    base_url = BASE_URL_APP.rstrip("/")

    return f"{base_url}/?token={token}"


def preparar_envios_whatsapp(supabase):
    permissionarios = buscar_permissionarios_ativos(supabase)

    lista_envios = []

    for p in permissionarios:
        permissionario_id = p.get("id")
        nome = p.get("nome")
        whatsapp = limpar_whatsapp(p.get("whatsapp"))

        if not permissionario_id:
            continue

        if not whatsapp:
            continue

        link = gerar_link_cotacao_permissionario(supabase, permissionario_id)

        lista_envios.append({
            "permissionario_id": permissionario_id,
            "nome": nome,
            "whatsapp": whatsapp,
            "link": link
        })

    return lista_envios


def tela_teste_links_whatsapp(supabase):
    st.title("Teste de Links do WhatsApp")

    st.info(
        "Esta tela mostra quais permissionários receberiam o link de cotação. "
        "Nenhuma mensagem será enviada nesta etapa."
    )

    lista_envios = preparar_envios_whatsapp(supabase)

    if not lista_envios:
        st.warning("Nenhum permissionário ativo encontrado para envio.")
        return

    st.success(f"{len(lista_envios)} permissionário(s) ativo(s) encontrado(s).")

    for item in lista_envios:
        with st.expander(item["nome"]):
            st.write("**ID:**", item["permissionario_id"])
            st.write("**WhatsApp:**", item["whatsapp"])
            st.write("**Link:**", item["link"])

            st.link_button(
                "Abrir link de cotação",
                item["link"]
            )