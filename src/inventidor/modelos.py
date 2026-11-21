"""Modelos de dados básicos: operações da nota de corretagem e resultados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class TipoAtivo(str, Enum):
    ACAO = "ACAO"
    FII = "FII"
    ETF = "ETF"


class Lado(str, Enum):
    COMPRA = "C"
    VENDA = "V"


class Modalidade(str, Enum):
    """Grupos separados para apuração e compensação de prejuízo."""

    COMUM = "COMUM"  # ações e ETFs fora de day trade
    DAY_TRADE = "DAY_TRADE"
    FII = "FII"


@dataclass(frozen=True)
class Operacao:
    """Uma linha da nota de corretagem."""

    data: date
    ticker: str
    tipo: TipoAtivo
    lado: Lado
    quantidade: int
    preco: Decimal
    custos: Decimal = Decimal("0")  # corretagem + emolumentos + taxas rateadas
    irrf: Decimal = Decimal("0")  # IR retido na fonte ("dedo-duro") informado na nota

    @property
    def valor_bruto(self) -> Decimal:
        return self.preco * self.quantidade


@dataclass
class ResultadoVenda:
    """Lucro ou prejuízo de uma venda (ou parte dela)."""

    data: date
    ticker: str
    tipo: TipoAtivo
    modalidade: Modalidade
    quantidade: int
    valor_venda: Decimal  # líquido de custos
    custo_aquisicao: Decimal  # inclui custos de compra
    irrf: Decimal = Decimal("0")
    valor_alienacao: Decimal = Decimal("0")  # valor bruto, usado no limite de isenção

    @property
    def resultado(self) -> Decimal:
        return self.valor_venda - self.custo_aquisicao


@dataclass
class Posicao:
    ticker: str
    tipo: TipoAtivo
    quantidade: int = 0
    custo_total: Decimal = Decimal("0")

    @property
    def preco_medio(self) -> Decimal:
        if self.quantidade == 0:
            return Decimal("0")
        return self.custo_total / self.quantidade


@dataclass
class Saldos:
    """Saldos que passam de um mês para o outro."""

    prejuizo: dict[Modalidade, Decimal] = field(
        default_factory=lambda: {m: Decimal("0") for m in Modalidade}
    )
    irrf_a_compensar: Decimal = Decimal("0")
    imposto_abaixo_minimo: Decimal = Decimal("0")  # DARF < R$ 10 acumulado
