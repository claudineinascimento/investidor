"""Cotações diárias pelo Yahoo Finance (fonte não oficial).

API: https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}.SA?range=1y&interval=1d
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from inventidor.dados.http import baixar
from inventidor.especialistas.tecnico import Candle

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?range={periodo}&interval=1d"
PERIODOS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
CENTAVO = Decimal("0.01")


def _dec(v) -> Decimal:
    return Decimal(str(v)).quantize(CENTAVO)


def simbolo_yahoo(ticker: str) -> str:
    t = ticker.strip().upper()
    return t if "." in t or t.startswith("^") else f"{t}.SA"


def parse_yahoo(resp: dict) -> list[Candle]:
    chart = (resp or {}).get("chart") or {}
    if chart.get("error") or not chart.get("result"):
        raise ValueError(f"Yahoo Finance não devolveu cotações: {chart.get('error') or 'resposta vazia'}")
    r = chart["result"][0]
    ts = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    fech, maxi, mini = q.get("close") or [], q.get("high") or [], q.get("low") or []
    if not (len(ts) == len(fech) == len(maxi) == len(mini)):
        raise ValueError("Yahoo Finance devolveu séries de tamanhos diferentes.")
    # Data no fuso da bolsa (B3: -3h), para não cair no dia errado.
    fuso = timezone(timedelta(seconds=(r.get("meta") or {}).get("gmtoffset", -3 * 3600)))
    por_dia: dict = {}
    for t, c, h, l in zip(ts, fech, maxi, mini):
        if None in (t, c, h, l):
            continue  # dia sem negociação ou cotação incompleta
        d = datetime.fromtimestamp(t, fuso).date()
        por_dia[d] = Candle(d, _dec(c), _dec(h), _dec(l))  # último ponto do dia prevalece
    return [por_dia[d] for d in sorted(por_dia)]


def baixar_cotacoes(ticker: str, periodo: str = "1y") -> list[Candle]:
    if periodo not in PERIODOS:
        raise ValueError(f"Período {periodo!r} inválido; use um de {sorted(PERIODOS)}.")
    simbolo = simbolo_yahoo(ticker)
    bruto = baixar(URL.format(simbolo=quote(simbolo), periodo=periodo), validade=1800)
    try:
        resp = json.loads(bruto)
    except json.JSONDecodeError as e:
        raise ValueError(f"Yahoo Finance devolveu algo que não é JSON para {simbolo}: {bruto[:200]!r}") from e
    candles = parse_yahoo(resp)
    if not candles:
        raise ValueError(f"Yahoo Finance não tem cotações de {simbolo} no período {periodo}.")
    return candles


def salvar_csv(series: dict[str, list[Candle]], caminho: str | Path) -> None:
    """Grava no formato lido por `tecnico.ler_precos` (data;ticker;fechamento;maxima;minima)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["data", "ticker", "fechamento", "maxima", "minima"])
        for t in sorted(series):
            for c in series[t]:
                w.writerow([c.data.isoformat(), t, c.fechamento, c.maxima, c.minima])
