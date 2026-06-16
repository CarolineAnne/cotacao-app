
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from supabase import create_client

from whatsapp_service import (
    carregar_config_whatsapp,
    enviar_para_permissionario
)


load_dotenv()

TZ = ZoneInfo("America/Bahia")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL e SUPABASE_KEY não foram configurados."
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def agora_brasil():
    return datetime.now(TZ)


def normalizar_hora(valor, padrao="07:00"):
    if not valor:
        return padrao

    valor = str(valor).strip()
    return valor[:5] if len(valor) >= 5 else padrao


def pode_enviar_agora(config):
    agora = agora_brasil()
    hora_atual = agora.strftime("%H:%M")

    hora_envio = normalizar_hora(
        config.get("hora_envio"),
        padrao="07:00"
    )

    hora_limite = normalizar_hora(
        config.get("hora_limite"),
        padrao="09:00"
    )

    if hora_atual < hora_envio:
        print(
            "Ainda não está no horário de envio. "
            f"Atual: {hora_atual} | Envio: {hora_envio}"
        )
        return False

    if hora_atual > hora_limite:
        print(
            "O horário limite já passou. "
            f"Atual: {hora_atual} | Limite: {hora_limite}"
        )
        return False

    return True


def buscar_permissionarios_ativos():
    resposta = (
        supabase
        .table("permissionarios")
        .select("id, nome, whatsapp, ativo")
        .eq("ativo", True)
        .execute()
    )

    return resposta.data or []


def automacao_whatsapp():
    agora = agora_brasil()

    print(
        "Verificando automação: "
        f"{agora.strftime('%d/%m/%Y %H:%M')}"
    )

    try:
        config = carregar_config_whatsapp(supabase)
    except Exception as erro:
        print(
            "Erro ao carregar a configuração: "
            f"{erro}"
        )
        return

    if not config.get("ativo", False):
        print("A automação está desativada.")
        return

    if not pode_enviar_agora(config):
        return

    try:
        permissionarios = buscar_permissionarios_ativos()
    except Exception as erro:
        print(
            "Erro ao buscar permissionários: "
            f"{erro}"
        )
        return

    if not permissionarios:
        print("Nenhum permissionário ativo encontrado.")
        return

    print(
        f"{len(permissionarios)} permissionário(s) "
        "ativo(s) encontrado(s)."
    )

    for permissionario in permissionarios:
        resultado = enviar_para_permissionario(
            supabase=supabase,
            permissionario=permissionario,
            config=config,
            registrar=True,
            impedir_duplicado=True
        )

        nome = permissionario.get(
            "nome",
            "Sem nome"
        )

        if resultado.get("ok"):
            print(
                f"Mensagem enviada para {nome}."
            )
        elif resultado.get("ignorado"):
            print(
                f"{nome}: {resultado.get('erro')}"
            )
        else:
            print(
                f"Erro no envio para {nome}: "
                f"{resultado.get('erro')}"
            )


if __name__ == "__main__":
    scheduler = BlockingScheduler(
        timezone=str(TZ)
    )

    scheduler.add_job(
        automacao_whatsapp,
        "interval",
        minutes=1,
        id="envio_whatsapp_cotacao",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )

    print("Automação do WhatsApp iniciada.")
    print(
        "O horário será verificado "
        "a cada 1 minuto."
    )

    automacao_whatsapp()
    scheduler.start()
