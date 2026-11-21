"""Download com cache local e erro explícito quando a rede não responde.

Nada é estimado no lugar de um dado que não chegou: sem rede, levanta
`RedeIndisponivel` e o comando avisa o usuário.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

CACHE_PADRAO = Path("dados/cache")
# Alguns serviços (Yahoo, CDN da CVM) recusam pedidos sem User-Agent de navegador.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class RedeIndisponivel(RuntimeError):
    """A fonte de dados não respondeu (sem internet, bloqueio ou erro do servidor)."""


def baixar(
    url: str,
    cache: str | Path | None = CACHE_PADRAO,
    validade: int = 3600,
    timeout: int = 60,
    cabecalhos: dict[str, str] | None = None,
) -> bytes:
    """Baixa `url`. Com `cache`, reaproveita a cópia local por `validade` segundos."""
    arquivo = None
    if cache is not None:
        arquivo = Path(cache) / hashlib.sha256(url.encode()).hexdigest()[:32]
        if arquivo.exists() and time.time() - arquivo.stat().st_mtime < validade:
            return arquivo.read_bytes()

    host = urlsplit(url).hostname or url
    pedido = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*", **(cabecalhos or {})}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resp:
            dados = resp.read()
    except urllib.error.HTTPError as e:
        raise RedeIndisponivel(f"{host} respondeu HTTP {e.code} ({e.reason})") from e
    except urllib.error.URLError as e:
        raise RedeIndisponivel(f"{host} inacessível ({e.reason})") from e
    except (TimeoutError, OSError) as e:
        raise RedeIndisponivel(f"{host} inacessível ({e})") from e

    if arquivo is not None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(dados)
    return dados
