"""Carteira: preço médio, posições e resultado de cada venda.

Regras adotadas (padrão da Receita Federal):
- Custos da compra entram no preço médio; custos da venda reduzem o valor de venda.
- Compra e venda do mesmo ativo no mesmo dia formam day trade até a menor
  das quantidades; o restante segue como operação comum.
- Venda sem posição (venda a descoberto) não é suportada nesta fase.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from itertools import groupby
from typing import Iterable

from inventidor.modelos import (
    Lado,
    Modalidade,
    Operacao,
    Posicao,
    ResultadoVenda,
    TipoAtivo,
)


class VendaSemPosicao(ValueError):
    pass


def _modalidade_comum(tipo: TipoAtivo) -> Modalidade:
    return Modalidade.FII if tipo == TipoAtivo.FII else Modalidade.COMUM


def _soma(ops: list[Operacao], attr: str) -> Decimal:
    return sum((getattr(o, attr) for o in ops), Decimal("0"))


class Carteira:
    def __init__(self) -> None:
        self.posicoes: dict[str, Posicao] = {}
        self.resultados: list[ResultadoVenda] = []

    def processar(self, operacoes: Iterable[Operacao]) -> "Carteira":
        ordenadas = sorted(operacoes, key=lambda o: (o.data, o.ticker))
        for (dia, ticker), grupo in groupby(ordenadas, key=lambda o: (o.data, o.ticker)):
            self._processar_dia(list(grupo))
        return self

    def _posicao(self, op: Operacao) -> Posicao:
        if op.ticker not in self.posicoes:
            self.posicoes[op.ticker] = Posicao(op.ticker, op.tipo)
        return self.posicoes[op.ticker]

    def _processar_dia(self, ops: list[Operacao]) -> None:
        compras = [o for o in ops if o.lado == Lado.COMPRA]
        vendas = [o for o in ops if o.lado == Lado.VENDA]
        ref = ops[0]
        qtd_c = sum(o.quantidade for o in compras)
        qtd_v = sum(o.quantidade for o in vendas)
        qtd_dt = min(qtd_c, qtd_v)

        # Valores médios do dia, já com custos.
        custo_c = _soma(compras, "valor_bruto") + _soma(compras, "custos")
        liquido_v = _soma(vendas, "valor_bruto") - _soma(vendas, "custos")
        irrf_v = _soma(vendas, "irrf")
        bruto_v = _soma(vendas, "valor_bruto")

        if qtd_dt:
            self.resultados.append(
                ResultadoVenda(
                    data=ref.data,
                    ticker=ref.ticker,
                    tipo=ref.tipo,
                    modalidade=(
                        Modalidade.FII if ref.tipo == TipoAtivo.FII else Modalidade.DAY_TRADE
                    ),
                    quantidade=qtd_dt,
                    valor_venda=liquido_v * qtd_dt / qtd_v,
                    custo_aquisicao=custo_c * qtd_dt / qtd_c,
                    irrf=irrf_v * qtd_dt / qtd_v,
                    valor_alienacao=bruto_v * qtd_dt / qtd_v,
                )
            )

        pos = self._posicao(ref)
        sobra_c = qtd_c - qtd_dt
        sobra_v = qtd_v - qtd_dt

        if sobra_v:
            if sobra_v > pos.quantidade:
                raise VendaSemPosicao(
                    f"{ref.data} {ref.ticker}: venda de {sobra_v} sem posição suficiente "
                    f"({pos.quantidade}). Importe as compras anteriores."
                )
            custo = pos.preco_medio * sobra_v
            self.resultados.append(
                ResultadoVenda(
                    data=ref.data,
                    ticker=ref.ticker,
                    tipo=ref.tipo,
                    modalidade=_modalidade_comum(ref.tipo),
                    quantidade=sobra_v,
                    valor_venda=liquido_v * sobra_v / qtd_v,
                    custo_aquisicao=custo,
                    irrf=irrf_v * sobra_v / qtd_v,
                    valor_alienacao=bruto_v * sobra_v / qtd_v,
                )
            )
            pos.quantidade -= sobra_v
            pos.custo_total -= custo

        if sobra_c:
            pos.quantidade += sobra_c
            pos.custo_total += custo_c * sobra_c / qtd_c

    def posicoes_abertas(self) -> list[Posicao]:
        return [p for p in self.posicoes.values() if p.quantidade > 0]

    def resultados_por_mes(self) -> dict[tuple[int, int], list[ResultadoVenda]]:
        meses: dict[tuple[int, int], list[ResultadoVenda]] = defaultdict(list)
        for r in self.resultados:
            meses[(r.data.year, r.data.month)].append(r)
        return dict(sorted(meses.items()))
