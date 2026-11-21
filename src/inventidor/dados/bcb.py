"""Banco Central (SGS): Selic meta, IPCA mensal e juro real.

API: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json
Resposta: [{"data": "dd/mm/aaaa", "valor": "15.00"}, ...]
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from inventidor.dados.http import baixar

SERIES = {
    "selic_meta": 432,  # meta Selic definida pelo Copom, % a.a.
    "ipca_mensal": 433,  # IPCA, variação % no mês
}
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"


def parse_serie(itens) -> list[tuple[date, Decimal]]:
    if not isinstance(itens, list) or not itens:
        raise ValueError(f"Resposta inesperada do Banco Central: {str(itens)[:200]}")
    serie = []
    for i in itens:
        try:
            serie.append((datetime.strptime(i["data"], "%d/%m/%Y").date(), Decimal(str(i["valor"]))))
        except (KeyError, TypeError, ValueError, InvalidOperation) as e:
            raise ValueError(f"Item inesperado na série do Banco Central: {i!r}") from e
    return sorted(serie)


def ultimos(nome: str, n: int) -> list[tuple[date, Decimal]]:
    codigo = SERIES[nome]
    bruto = baixar(URL.format(codigo=codigo, n=n), validade=6 * 3600)
    try:
        itens = json.loads(bruto.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"Banco Central devolveu algo que não é JSON (série {codigo}): {bruto[:200]!r}") from e
    serie = parse_serie(itens)
    if len(serie) < n:
        raise ValueError(f"Série {codigo} veio com {len(serie)} pontos; esperados {n}.")
    return serie[-n:]


def ipca_12_meses(serie: list[tuple[date, Decimal]]) -> Decimal:
    """IPCA acumulado nos últimos 12 meses, composto (em %)."""
    if len(serie) < 12:
        raise ValueError(f"IPCA de 12 meses precisa de 12 meses; vieram {len(serie)}.")
    fator = Decimal(1)
    for _, v in serie[-12:]:
        fator *= 1 + v / 100
    return (fator - 1) * 100


def juro_real(selic: Decimal, ipca: Decimal) -> Decimal:
    """Juro real pela fórmula de Fisher, em %."""
    return ((1 + selic / 100) / (1 + ipca / 100) - 1) * 100
