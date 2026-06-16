
import os
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


load_dotenv()

TZ = ZoneInfo("America/Bahia")


def agora_brasil():
    return datetime.now(TZ)


def data_hoje_brasil():
    return agora_brasil().date()


def normalizar_hora(valor, padrao="07:00"):
    if not valor:
        return padrao

    valor = str(valor).strip()
    return valor[:5] if len(valor) >= 5 else padrao


def limpar_whatsapp(numero):
    if not numero:
        return None

    numero_limpo = re.sub(r"\D", "", str(numero))

    if numero_limpo.startswith("55"):
        return numero_limpo

    if len(numero_limpo) in (10, 11):
        return "55" + numero_limpo

    return numero_limpo or None


def carregar_config_whatsapp(supabase):
    resposta = (
        supabase
        .table("config_permissionarios")
        .select("*")
        .eq("id", 1)
        .limit(1)
        .execute()
    )

    if resposta.data:
        return resposta.data[0]

    return {
        "id": 1,
        "ativo": False,
        "hora_envio": "07:00:00",
        "hora_limite": "09:00:00",
        "mensagem": (
            "Bom dia! Por favor, informe os preços dos produtos "
            "solicitados para a cotação de hoje."
        ),
        "base_url": "",
        "template_nome": "link_cotacao_diaria",
        "idioma": "pt_BR"
    }


def montar_validade_link(config):
    hora_limite_txt = normalizar_hora(
        config.get("hora_limite"),
        padrao="09:00"
    )

    hora_limite = datetime.strptime(
        hora_limite_txt,
        "%H:%M"
    ).time()

    return datetime.combine(
        data_hoje_brasil(),
        hora_limite,
        tzinfo=TZ
    )


def gerar_ou_atualizar_link(supabase, permissionario_id, config):
    data_hoje = data_hoje_brasil().isoformat()
    valido_ate = montar_validade_link(config)

    base_url = str(config.get("base_url") or "").strip().rstrip("/")

    if not base_url:
        raise ValueError(
            "A URL base do sistema não está configurada."
        )

    resposta = (
        supabase
        .table("links_permissionarios")
        .select("*")
        .eq("permissionario_id", int(permissionario_id))
        .eq("data", data_hoje)
        .limit(1)
        .execute()
    )

    if resposta.data:
        link_existente = resposta.data[0]
        token = link_existente["token"]

        (
            supabase
            .table("links_permissionarios")
            .update({
                "valido_ate": valido_ate.isoformat(),
                "usado": False
            })
            .eq("id", link_existente["id"])
            .execute()
        )
    else:
        token = uuid.uuid4().hex

        (
            supabase
            .table("links_permissionarios")
            .insert({
                "permissionario_id": int(permissionario_id),
                "data": data_hoje,
                "token": token,
                "valido_ate": valido_ate.isoformat(),
                "usado": False
            })
            .execute()
        )

    return f"{base_url}?token={token}", valido_ate


def enviar_template_whatsapp(
    telefone,
    nome,
    mensagem,
    link,
    valido_ate,
    config
):
    token = os.getenv("WHATSAPP_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_version = os.getenv("WHATSAPP_API_VERSION", "v25.0")

    if not token or not phone_number_id:
        raise ValueError(
            "WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID "
            "não foram configurados."
        )

    template_nome = str(
        config.get("template_nome")
        or os.getenv(
            "WHATSAPP_TEMPLATE_NAME",
            "link_cotacao_diaria"
        )
    ).strip()

    idioma = str(
        config.get("idioma")
        or os.getenv(
            "WHATSAPP_TEMPLATE_LANGUAGE",
            "pt_BR"
        )
    ).strip()

    url = (
        f"https://graph.facebook.com/"
        f"{api_version}/{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": limpar_whatsapp(telefone),
        "type": "template",
        "template": {
            "name": template_nome,
            "language": {
                "code": idioma
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(nome)
                        },
                        {
                            "type": "text",
                            "text": str(mensagem)
                        },
                        {
                            "type": "text",
                            "text": str(link)
                        },
                        {
                            "type": "text",
                            "text": valido_ate.strftime("%H:%M")
                        }
                    ]
                }
            ]
        }
    }

    resposta = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    try:
        dados_resposta = resposta.json()
    except Exception:
        dados_resposta = {
            "resposta": resposta.text
        }

    return resposta.status_code, dados_resposta


def envio_ja_realizado(
    supabase,
    permissionario_id,
    data_cotacao
):
    resposta = (
        supabase
        .table("disparos_whatsapp")
        .select("id")
        .eq("permissionario_id", int(permissionario_id))
        .eq("data_cotacao", data_cotacao)
        .eq("status", "enviado")
        .limit(1)
        .execute()
    )

    return bool(resposta.data)


def registrar_disparo(
    supabase,
    data_cotacao,
    permissionario_id,
    permissionario_nome,
    whatsapp,
    link,
    status,
    message_id=None,
    erro=None
):
    dados = {
        "data_cotacao": data_cotacao,
        "permissionario_id": int(permissionario_id),
        "permissionario_nome": permissionario_nome,
        "whatsapp": whatsapp,
        "link": link,
        "status": status,
        "message_id": message_id,
        "erro": erro,
        "enviado_em": agora_brasil().isoformat()
    }

    resposta = (
        supabase
        .table("disparos_whatsapp")
        .select("id")
        .eq("data_cotacao", data_cotacao)
        .eq("permissionario_id", int(permissionario_id))
        .limit(1)
        .execute()
    )

    if resposta.data:
        (
            supabase
            .table("disparos_whatsapp")
            .update(dados)
            .eq("id", resposta.data[0]["id"])
            .execute()
        )
    else:
        (
            supabase
            .table("disparos_whatsapp")
            .insert(dados)
            .execute()
        )


def enviar_para_permissionario(
    supabase,
    permissionario,
    config=None,
    registrar=True,
    impedir_duplicado=True
):
    if config is None:
        config = carregar_config_whatsapp(supabase)

    permissionario_id = permissionario.get("id")
    nome = str(permissionario.get("nome") or "").strip()
    whatsapp = limpar_whatsapp(
        permissionario.get("whatsapp")
    )

    if not permissionario_id:
        return {
            "ok": False,
            "erro": "Permissionário sem ID."
        }

    if not nome:
        return {
            "ok": False,
            "erro": "Permissionário sem nome."
        }

    if not whatsapp:
        return {
            "ok": False,
            "erro": "Permissionário sem WhatsApp válido."
        }

    data_cotacao = data_hoje_brasil().isoformat()

    if impedir_duplicado and envio_ja_realizado(
        supabase,
        permissionario_id,
        data_cotacao
    ):
        return {
            "ok": False,
            "ignorado": True,
            "erro": "Mensagem já enviada hoje."
        }

    mensagem = str(config.get("mensagem") or "").strip()

    if not mensagem:
        mensagem = (
            "Bom dia! Por favor, informe os preços dos produtos "
            "solicitados para a cotação de hoje."
        )

    link = ""

    try:
        link, valido_ate = gerar_ou_atualizar_link(
            supabase,
            permissionario_id,
            config
        )

        status_code, resposta = enviar_template_whatsapp(
            telefone=whatsapp,
            nome=nome,
            mensagem=mensagem,
            link=link,
            valido_ate=valido_ate,
            config=config
        )

        if status_code in (200, 201):
            message_id = None

            try:
                message_id = (
                    resposta
                    .get("messages", [{}])[0]
                    .get("id")
                )
            except Exception:
                pass

            if registrar:
                registrar_disparo(
                    supabase=supabase,
                    data_cotacao=data_cotacao,
                    permissionario_id=permissionario_id,
                    permissionario_nome=nome,
                    whatsapp=whatsapp,
                    link=link,
                    status="enviado",
                    message_id=message_id,
                    erro=None
                )

            return {
                "ok": True,
                "status_code": status_code,
                "resposta": resposta,
                "message_id": message_id,
                "link": link,
                "valido_ate": valido_ate
            }

        if registrar:
            registrar_disparo(
                supabase=supabase,
                data_cotacao=data_cotacao,
                permissionario_id=permissionario_id,
                permissionario_nome=nome,
                whatsapp=whatsapp,
                link=link,
                status="erro",
                message_id=None,
                erro=str(resposta)
            )

        return {
            "ok": False,
            "status_code": status_code,
            "resposta": resposta,
            "erro": str(resposta),
            "link": link
        }

    except Exception as erro:
        if registrar:
            try:
                registrar_disparo(
                    supabase=supabase,
                    data_cotacao=data_cotacao,
                    permissionario_id=permissionario_id,
                    permissionario_nome=nome,
                    whatsapp=whatsapp,
                    link=link,
                    status="erro",
                    message_id=None,
                    erro=str(erro)
                )
            except Exception:
                pass

        return {
            "ok": False,
            "erro": str(erro),
            "link": link
        }
