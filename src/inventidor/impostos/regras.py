"""Tabela de regras do IR sobre renda variável.

As regras ficam em dados, não espalhadas no código, porque a tributação de
renda variável muda. Ao mudar a lei, crie uma nova instância com a data de
início de vigência e adicione-a em REGRAS. Valide sempre com um contador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from inventidor.modelos import Modalidade


@dataclass(frozen=True)
class RegrasIR:
    vigencia_inicio: date
    aliquota: dict[Modalidade, Decimal]
    # Isenção para vendas mensais de AÇÕES (operações comuns) até este valor.
    limite_isencao_acoes: Decimal
    # Alíquota do IRRF "dedo-duro" sobre o valor de venda em operações comuns.
    irrf_comum: Decimal
    # Alíquota do IRRF sobre o lucro de day trade.
    irrf_day_trade: Decimal
    darf_minimo: Decimal
    codigo_darf: str
    # Entendimento adotado: prejuízo em mês isento entra no saldo a compensar.
    # Confirme com seu contador; mude para False se ele orientar diferente.
    compensar_prejuizo_mes_isento: bool = True


REGRAS: list[RegrasIR] = [
    RegrasIR(
        vigencia_inicio=date(2005, 1, 1),
        aliquota={
            Modalidade.COMUM: Decimal("0.15"),
            Modalidade.DAY_TRADE: Decimal("0.20"),
            Modalidade.FII: Decimal("0.20"),
        },
        limite_isencao_acoes=Decimal("20000"),
        irrf_comum=Decimal("0.00005"),
        irrf_day_trade=Decimal("0.01"),
        darf_minimo=Decimal("10"),
        codigo_darf="6015",
    ),
]


def regras_vigentes(em: date) -> RegrasIR:
    validas = [r for r in REGRAS if r.vigencia_inicio <= em]
    if not validas:
        raise ValueError(f"Nenhuma regra de IR vigente em {em}")
    return max(validas, key=lambda r: r.vigencia_inicio)
