"""Analista Fundamentalista: filtros de qualidade, nota e preço justo.

Entrada: tabela de indicadores por empresa (CSV hoje; na próxima etapa, dados
da CVM e de provedores de cotação). A nota é uma soma de critérios simples e
transparentes, para que o agente consiga explicar cada ponto.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from inventidor.importador import _decimal

ZERO = Decimal("0")
TAXA_BAZIN = Decimal("0.06")  # dividendo mínimo desejado de 6% ao ano
LIQUIDEZ_MINIMA = Decimal("1000000")  # R$ 1 milhão negociados por dia


@dataclass(frozen=True)
class Fundamentos:
    ticker: str
    setor: str
    preco: Decimal
    lpa: Decimal  # lucro por ação (12 meses)
    vpa: Decimal  # valor patrimonial por ação
    dpa: Decimal  # dividendos por ação (12 meses)
    roe: Decimal  # em %, ex.: 18 = 18%
    margem_liquida: Decimal  # em %
    div_liq_ebitda: Decimal  # dívida líquida / EBITDA
    cresc_lucro_5a: Decimal  # crescimento anual médio do lucro, em %
    liquidez_diaria: Decimal  # R$ negociados por dia

    @property
    def pl(self) -> Decimal | None:
        return self.preco / self.lpa if self.lpa > 0 else None

    @property
    def pvp(self) -> Decimal | None:
        return self.preco / self.vpa if self.vpa > 0 else None

    @property
    def dividend_yield(self) -> Decimal:
        return self.dpa / self.preco * 100 if self.preco else ZERO


@dataclass
class Avaliacao:
    fundamentos: Fundamentos
    nota: int  # 0 a 10
    pontos: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    aprovada: bool = True
    preco_graham: Decimal | None = None
    preco_bazin: Decimal | None = None

    @property
    def preco_justo(self) -> Decimal | None:
        valores = [v for v in (self.preco_graham, self.preco_bazin) if v]
        return sum(valores, ZERO) / len(valores) if valores else None

    @property
    def margem_seguranca(self) -> Decimal | None:
        """% de desconto do preço atual em relação ao preço justo."""
        pj = self.preco_justo
        if not pj:
            return None
        return (pj - self.fundamentos.preco) / pj * 100


def ler_fundamentos(caminho: str | Path) -> list[Fundamentos]:
    linhas = Path(caminho).read_text(encoding="utf-8-sig").splitlines()
    sep = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    saida = []
    for l in csv.DictReader(linhas, delimiter=sep):
        l = {k.strip().lower(): v for k, v in l.items()}
        saida.append(
            Fundamentos(
                ticker=l["ticker"].strip().upper(),
                setor=l["setor"].strip(),
                **{
                    k: _decimal(l[k])
                    for k in (
                        "preco", "lpa", "vpa", "dpa", "roe", "margem_liquida",
                        "div_liq_ebitda", "cresc_lucro_5a", "liquidez_diaria",
                    )
                },
            )
        )
    return saida


def avaliar(f: Fundamentos) -> Avaliacao:
    av = Avaliacao(fundamentos=f, nota=0)

    # Filtros eliminatórios.
    if f.lpa <= 0:
        av.alertas.append("Empresa com prejuízo nos últimos 12 meses.")
        av.aprovada = False
    if f.div_liq_ebitda > 3:
        av.alertas.append(f"Dívida alta: {f.div_liq_ebitda}x o EBITDA (limite 3x).")
        av.aprovada = False
    if f.liquidez_diaria < LIQUIDEZ_MINIMA:
        av.alertas.append("Pouca liquidez: pode ser difícil vender quando precisar.")
        av.aprovada = False

    criterios = [
        (f.roe >= 15, f"ROE de {f.roe}% (rentabilidade alta)"),
        (f.roe >= 20, "ROE acima de 20%"),
        (f.margem_liquida >= 10, f"Margem líquida de {f.margem_liquida}%"),
        (f.div_liq_ebitda <= 1, "Dívida baixa (até 1x o EBITDA)"),
        (f.cresc_lucro_5a >= 5, f"Lucro cresce {f.cresc_lucro_5a}% ao ano"),
        (f.cresc_lucro_5a >= 10, "Crescimento acima de 10% ao ano"),
        (f.dividend_yield >= 5, f"Dividend yield de {f.dividend_yield:.1f}%"),
        (f.pl is not None and f.pl <= 12, f"P/L de {f.pl:.1f}" if f.pl else ""),
        (f.pvp is not None and f.pvp <= 2, f"P/VP de {f.pvp:.2f}" if f.pvp else ""),
        (f.liquidez_diaria >= 10 * LIQUIDEZ_MINIMA, "Liquidez alta"),
    ]
    for ok, texto in criterios:
        if ok:
            av.nota += 1
            av.pontos.append(texto)

    if f.lpa > 0 and f.vpa > 0:
        av.preco_graham = (Decimal("22.5") * f.lpa * f.vpa).sqrt().quantize(Decimal("0.01"))
    if f.dpa > 0:
        av.preco_bazin = (f.dpa / TAXA_BAZIN).quantize(Decimal("0.01"))
    return av


def ranking(empresas: list[Fundamentos]) -> list[Avaliacao]:
    """Aprovadas primeiro, por nota e depois por margem de segurança."""
    avs = [avaliar(f) for f in empresas]
    return sorted(
        avs,
        key=lambda a: (a.aprovada, a.nota, a.margem_seguranca or Decimal("-999")),
        reverse=True,
    )
