"""Quant / Backtest: testa a estratégia do Analista Técnico no passado.

Regras da simulação (propositalmente conservadoras e simples):
- O sinal "Zona de compra" no fechamento do dia t gera uma ordem limitada no
  preço de entrada, válida só no dia t+1 (executa se a mínima do dia chegar lá).
- Depois de entrar: sai no stop se a mínima o atingir (se stop e alvo caírem no
  mesmo dia, vale o stop), ou no alvo se a máxima o atingir, ou no fechamento do
  dia MAX_DIAS.
- Uma posição por vez por ação. Sem custos, sem imposto e sem dividendos.
Resultado passado não garante resultado futuro; backtest com poucas operações
quase nada prova. O relatório mostra a quantidade para isso ficar claro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from inventidor.especialistas.tecnico import Candle, Sinal, analisar

ZERO = Decimal("0")
MAX_DIAS = 40
JANELA_MINIMA = 60


@dataclass(frozen=True)
class Trade:
    ticker: str
    entrada_data: date
    entrada: Decimal
    saida_data: date
    saida: Decimal
    motivo: str  # "stop", "alvo" ou "prazo"

    @property
    def retorno_pct(self) -> Decimal:
        return (self.saida - self.entrada) / self.entrada * 100


def simular_trade(
    ticker: str, candles: list[Candle], inicio: int, entrada: Decimal, stop: Decimal, alvo: Decimal
) -> Trade | None:
    """Ordem limitada válida em candles[inicio]; depois, acompanha até sair."""
    c = candles[inicio]
    if c.minima > entrada:
        return None  # a ação não recuou até o preço limite
    preco_entrada = min(entrada, c.maxima)  # se abriu abaixo do limite, a ordem pega o limite
    ult = candles[min(inicio + MAX_DIAS, len(candles) - 1)]
    for d in candles[inicio : inicio + MAX_DIAS + 1]:
        if d.minima <= stop:
            return Trade(ticker, c.data, preco_entrada, d.data, stop, "stop")
        if d.maxima >= alvo and d is not c:
            return Trade(ticker, c.data, preco_entrada, d.data, alvo, "alvo")
    return Trade(ticker, c.data, preco_entrada, ult.data, ult.fechamento, "prazo")


def backtest(ticker: str, candles: list[Candle]) -> list[Trade]:
    trades: list[Trade] = []
    livre_a_partir = 0
    for t in range(JANELA_MINIMA, len(candles) - 1):
        if t < livre_a_partir:
            continue
        leitura = analisar(ticker, candles[: t + 1])
        if leitura.sinal != Sinal.COMPRAR:
            continue
        trade = simular_trade(
            ticker, candles, t + 1, leitura.entrada_max, leitura.stop, leitura.alvo
        )
        if trade:
            trades.append(trade)
            saida_idx = next(i for i, c in enumerate(candles) if c.data == trade.saida_data)
            livre_a_partir = saida_idx + 1
    return trades


@dataclass(frozen=True)
class Resumo:
    ticker: str
    operacoes: int
    acertos: int
    retorno_medio_pct: Decimal
    retorno_acumulado_pct: Decimal
    perda_maxima_pct: Decimal  # maior queda da curva de capital, em %
    buy_and_hold_pct: Decimal  # primeira à última cotação do período testado

    @property
    def taxa_acerto(self) -> Decimal:
        return Decimal(self.acertos) / self.operacoes * 100 if self.operacoes else ZERO


def resumir(ticker: str, candles: list[Candle], trades: list[Trade]) -> Resumo:
    base = candles[JANELA_MINIMA]
    bh = (candles[-1].fechamento - base.fechamento) / base.fechamento * 100
    if not trades:
        return Resumo(ticker, 0, 0, ZERO, ZERO, ZERO, bh)
    capital = Decimal("1")
    pico = capital
    pior = ZERO
    for t in trades:
        capital *= 1 + t.retorno_pct / 100
        pico = max(pico, capital)
        pior = max(pior, (pico - capital) / pico * 100)
    return Resumo(
        ticker=ticker,
        operacoes=len(trades),
        acertos=sum(1 for t in trades if t.retorno_pct > 0),
        retorno_medio_pct=sum((t.retorno_pct for t in trades), ZERO) / len(trades),
        retorno_acumulado_pct=(capital - 1) * 100,
        perda_maxima_pct=pior,
        buy_and_hold_pct=bh,
    )


def texto_resumos(resumos: list[Resumo]) -> str:
    l = [
        "Backtest do Analista Técnico (sem custos, imposto ou dividendos)",
        f"{'Ação':<7}{'Oper.':>6}{'Acerto':>8}{'Médio':>8}{'Acumul.':>9}{'Perda máx.':>11}{'Comprar e segurar':>19}",
    ]
    for r in resumos:
        l.append(
            f"{r.ticker:<7}{r.operacoes:>6}{r.taxa_acerto:>7.0f}%{r.retorno_medio_pct:>7.1f}%"
            f"{r.retorno_acumulado_pct:>8.1f}%{r.perda_maxima_pct:>10.1f}%{r.buy_and_hold_pct:>18.1f}%"
        )
    total = sum(r.operacoes for r in resumos)
    l.append(f"Total de operações: {total}. Poucas operações não permitem concluir nada.")
    return "\n".join(l)
