"""Analista Técnico: tendência, suporte, resistência e níveis de entrada, alvo e stop.

Indicadores simples e conhecidos (médias móveis, máximas e mínimas de 20 dias,
ATR de 14 dias). O objetivo não é prever preço, e sim evitar comprar no topo
de uma alta esticada e definir de antemão onde sair se a tese der errado.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path

from inventidor.importador import _data, _decimal

D2 = Decimal("0.01")


class Sinal(str, Enum):
    COMPRAR = "Zona de compra"
    AGUARDAR = "Aguardar recuo"
    EVITAR = "Evitar (tendência de baixa)"
    SEM_DADOS = "Histórico insuficiente"


@dataclass(frozen=True)
class Candle:
    data: date
    fechamento: Decimal
    maxima: Decimal
    minima: Decimal


@dataclass
class Leitura:
    ticker: str
    data: date
    preco: Decimal
    sinal: Sinal
    mm20: Decimal | None = None
    mm50: Decimal | None = None
    mm200: Decimal | None = None
    suporte: Decimal | None = None
    resistencia: Decimal | None = None
    atr: Decimal | None = None
    entrada_min: Decimal | None = None
    entrada_max: Decimal | None = None
    stop: Decimal | None = None
    alvo: Decimal | None = None
    motivo: str = ""

    @property
    def risco_pct(self) -> Decimal | None:
        """Queda do topo da faixa de entrada até o stop, em %."""
        if not (self.entrada_max and self.stop):
            return None
        return (self.entrada_max - self.stop) / self.entrada_max * 100


def ler_precos(caminho: str | Path) -> dict[str, list[Candle]]:
    linhas = Path(caminho).read_text(encoding="utf-8-sig").splitlines()
    sep = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    series: dict[str, list[Candle]] = defaultdict(list)
    for l in csv.DictReader(linhas, delimiter=sep):
        l = {k.strip().lower(): v for k, v in l.items()}
        series[l["ticker"].strip().upper()].append(
            Candle(_data(l["data"]), _decimal(l["fechamento"]), _decimal(l["maxima"]), _decimal(l["minima"]))
        )
    return {t: sorted(c, key=lambda x: x.data) for t, c in series.items()}


def _media(valores: list[Decimal]) -> Decimal:
    return sum(valores, Decimal("0")) / len(valores)


def _atr(candles: list[Candle], n: int = 14) -> Decimal:
    trs = []
    for ant, c in zip(candles[-n - 1 : -1], candles[-n:]):
        trs.append(max(c.maxima - c.minima, abs(c.maxima - ant.fechamento), abs(c.minima - ant.fechamento)))
    return _media(trs)


def analisar(ticker: str, candles: list[Candle]) -> Leitura:
    ult = candles[-1]
    if len(candles) < 60:
        return Leitura(ticker, ult.data, ult.fechamento, Sinal.SEM_DADOS, motivo="Menos de 60 pregões.")

    fech = [c.fechamento for c in candles]
    mm20, mm50 = _media(fech[-20:]), _media(fech[-50:])
    mm200 = _media(fech[-200:]) if len(fech) >= 200 else None
    mm50_antes = _media(fech[-60:-10])
    suporte = min(c.minima for c in candles[-20:])
    resistencia = max(c.maxima for c in candles[-20:])
    atr = _atr(candles)
    preco = ult.fechamento

    alta = preco > mm50 and mm50 > mm50_antes and (mm200 is None or mm50 > mm200)
    l = Leitura(
        ticker, ult.data, preco, Sinal.AGUARDAR,
        mm20=mm20.quantize(D2), mm50=mm50.quantize(D2),
        mm200=mm200.quantize(D2) if mm200 else None,
        suporte=suporte, resistencia=resistencia, atr=atr.quantize(D2),
    )

    if not alta:
        l.sinal = Sinal.EVITAR
        l.motivo = "Preço abaixo da média de 50 dias ou média caindo."
        return l

    # Faixa de entrada: entre a média de 20 dias e o preço, sem passar 1 ATR acima dela.
    l.entrada_min = min(mm20, preco).quantize(D2)
    l.entrada_max = min(preco, mm20 + atr).quantize(D2)
    l.stop = min(suporte, l.entrada_min - 2 * atr).quantize(D2)
    l.alvo = (l.entrada_max + 2 * (l.entrada_max - l.stop)).quantize(D2)

    esticado = (preco - mm20) / mm20 * 100
    if esticado > 6:
        l.sinal = Sinal.AGUARDAR
        l.motivo = f"Tendência de alta, mas {esticado:.1f}% acima da média de 20 dias: espere recuo até R$ {l.entrada_max}."
    else:
        l.sinal = Sinal.COMPRAR
        l.motivo = "Tendência de alta e preço perto da média de 20 dias."
    return l
