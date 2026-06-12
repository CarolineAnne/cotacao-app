import json
import re

from datetime import datetime
from zoneinfo import ZoneInfo


def normalizar_lista_precos(valor):
    if valor is None or valor == "":
        return []

    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except Exception:
            return []

    if not isinstance(valor, list):
        return []

    lista = []

    for p in valor:
        try:
            p = float(p)

            if p > 0:
                lista.append(p)

        except Exception:
            pass

    return lista


def data_hoje_brasil():
    return datetime.now(ZoneInfo("America/Bahia")).date()


def corrigir_classe(valor):
    valor = str(valor).strip().upper()

    if valor in ["HORTALIÇAS", "HORTALICAS"]:
        return "Hortaliças"

    elif valor == "FRUTAS":
        return "Frutas"

    elif valor == "ESPECIARIAS":
        return "Especiarias"

    elif valor == "CEREAIS":
        return "Cereais"

    else:
        return "SEM CLASSE"


def limpar_whatsapp(numero):
    if not numero:
        return None

    numero_limpo = re.sub(r"\D", "", str(numero))

    if numero_limpo.startswith("55"):
        return numero_limpo

    if len(numero_limpo) in [10, 11]:
        return "55" + numero_limpo

    return numero_limpo