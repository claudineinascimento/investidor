"""Vigia de posições: avisa quando o stop ou o alvo de uma posição foi atingido.

Os níveis vêm das compras que você registrou como executadas na fila (diário).
Quando um nível é atingido, o vigia sugere a venda (que entra na fila e só
acontece se você aprovar) e estima o imposto que essa venda geraria no mês,
usando o próprio Contador. Posições sem stop registrado não são vigiadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from enum import Enum

from inventidor.carteira import Carteira
from inventidor.diario import Estado, Item
from inventidor.impostos.apuracao import apurar_periodo
from inventidor.modelos import Lado, Operacao, TipoAtivo
from inventidor.especialistas.tecnico import Candle

D2 = Decimal("0.01")
FOLGA_VENDA = Decimal("0.995")  # piso 0,5% abaixo do último preço, para a ordem limitada executar


class Gatilho(str, Enum):
    STOP = "STOP"
    ALVO = "ALVO"


@dataclass(frozen=True)
class SinalVenda:
    ticker: str
    gatilho: Gatilho
    preco_atual: Decimal
    nivel: Decimal
    quantidade: int
    preco_minimo: Decimal
    resultado_estimado: Decimal
    imposto_adicional: Decimal
    nota: str


def niveis_ativos(itens: dict[str, Item]) -> dict[str, tuple[Decimal, Decimal]]:
    """(stop, alvo) da compra executada mais recente de cada ticker."""
    execs = sorted(
        (i for i in itens.values() if i.estado == Estado.EXECUTADA and i.lado == "C"),
        key=lambda i: (i.execucao or {}).get("data", ""),
    )
    return {i.ticker: (i.stop, i.alvo) for i in execs}


def _imposto_do_mes(ops: list[Operacao], ano: int, mes: int) -> Decimal:
    for ap in apurar_periodo(Carteira().processar(ops)):
        if (ap.ano, ap.mes) == (ano, mes):
            return ap.imposto_a_pagar
    return Decimal("0")


def vigiar(
    operacoes: list[Operacao],
    precos: dict[str, list[Candle]],
    itens: dict[str, Item],
    hoje: date | None = None,
) -> list[SinalVenda]:
    carteira = Carteira().processar(operacoes)
    niveis = niveis_ativos(itens)
    hoje = hoje or date.today()
    sinais: list[SinalVenda] = []
    for pos in carteira.posicoes_abertas():
        if pos.ticker not in niveis or not precos.get(pos.ticker):
            continue
        stop, alvo = niveis[pos.ticker]
        ult = precos[pos.ticker][-1]
        if ult.minima <= stop:
            gatilho, nivel, qtd = Gatilho.STOP, stop, pos.quantidade
        elif ult.maxima >= alvo:
            gatilho, nivel = Gatilho.ALVO, alvo
            qtd = max(1, int((Decimal(pos.quantidade) / 2).to_integral_value(rounding=ROUND_DOWN)))
        else:
            continue
        piso = (ult.fechamento * FOLGA_VENDA).quantize(D2)
        hipotetica = Operacao(hoje, pos.ticker, pos.tipo, Lado.VENDA, qtd, piso)
        antes = _imposto_do_mes(operacoes, hoje.year, hoje.month)
        depois = _imposto_do_mes(operacoes + [hipotetica], hoje.year, hoje.month)
        resultado = (piso - pos.preco_medio) * qtd
        nota = (
            "Stop atingido: a tese falhou. Sair limita a perda; esperar costuma aumentá-la."
            if gatilho == Gatilho.STOP
            else "Alvo atingido: sugiro vender metade e deixar o resto, subindo o stop para o preço médio."
        )
        sinais.append(SinalVenda(
            pos.ticker, gatilho, ult.fechamento, nivel, qtd, piso,
            resultado.quantize(D2), (depois - antes).quantize(D2), nota,
        ))
    return sinais


def itens_de_venda(sinais: list[SinalVenda], dia: date, tipos: dict[str, TipoAtivo] | None = None) -> list[Item]:
    return [
        Item(
            id=f"{dia:%Y%m%d}-V-{s.ticker}", data=dia, ticker=s.ticker,
            tipo=(tipos or {}).get(s.ticker, TipoAtivo.ACAO).value, quantidade=s.quantidade,
            preco_limite=s.preco_minimo, stop=s.nivel, alvo=s.nivel,
            tese=s.nota, parecer_risco=f"{s.gatilho.value} em R$ {s.nivel}", lado="V",
        )
        for s in sinais
    ]


def texto_sinais(sinais: list[SinalVenda]) -> str:
    if not sinais:
        return "Nenhuma posição atingiu stop ou alvo."
    l = ["Vigia de posições"]
    for s in sinais:
        l.append(
            f"  [{s.gatilho.value}] {s.ticker}: último R$ {s.preco_atual}, nível R$ {s.nivel}. "
            f"Vender {s.quantidade} a partir de R$ {s.preco_minimo}."
        )
        l.append(f"      Resultado estimado R$ {s.resultado_estimado}; imposto adicional no mês R$ {s.imposto_adicional}.")
        l.append(f"      {s.nota}")
    return "\n".join(l)
