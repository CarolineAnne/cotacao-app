def normalizar_base_url_publica(base_url):
    base_url = str(base_url or "").strip().rstrip("/")

    if not base_url:
        raise ValueError("A URL do sistema publicado não foi configurada.")

    if not base_url.lower().startswith("https://"):
        raise ValueError("A URL do sistema publicado deve começar com https://.")

    return base_url
