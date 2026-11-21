"""Gestor de Risco: aprova, ajusta ou veta cada sugestão de compra.

Checagens, em ordem:
1. Stop muito distante (mais de 15% de queda até o stop): veta.
2. Concentração por ação: no máximo o limite da política sobre a parcela de ações.
3. Concentração por setor: no máximo 40% da parcela de ações.
4. Perda até o stop: no máximo 2% do patrimônio investido por operação.
Quando dá para reduzir o valor e cumprir os limites, ajusta; senão, veta.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from inventidor.especialistas.consultor import Politica

ZERO = Decimal("0")
STOP_MAXIMO_PCT = Decimal("15")
RISCO_MAX_POR_OPERACAO = Decimal("0.02")
VALOR_MINIMO = Decimal("100")  # abaixo disso a corretagem e o esforço não compensam


class Veredito(str, Enum):
    APROVADO = "APROVADO"
    AJUSTADO = "AJUSTADO"
    VETADO = "VETADO"


@dataclass(frozen=True)
class Parecer:
    veredito: Veredito
    valor: Decimal
    motivos: tuple[str, ...]


def avaliar_compra(
    *,
    ticker: str,
    setor: str,
    valor: Decimal,
    risco_pct: Decimal | None,
    politica: Politica,
    parcela_acoes_alvo: Decimal,
    patrimonio_investido: Decimal,
    posicoes: dict[str, tuple[str, Decimal]],  # ticker -> (setor, valor atual)
) -> Parecer:
    motivos: list[str] = []
    original = valor

    if risco_pct is None:
        return Parecer(Veredito.VETADO, ZERO, ("Sem stop definido pelo Analista Técnico.",))
    if risco_pct > STOP_MAXIMO_PCT:
        return Parecer(
            Veredito.VETADO, ZERO,
            (f"Stop a {risco_pct:.1f}% do preço: volatilidade alta demais (limite {STOP_MAXIMO_PCT}%).",),
        )

    ja_tem = posicoes.get(ticker, (setor, ZERO))[1]
    teto_acao = politica.limite_por_acao * parcela_acoes_alvo - ja_tem
    if valor > teto_acao:
        valor = max(ZERO, teto_acao)
        motivos.append(
            f"Limite por ação: {politica.limite_por_acao * 100:.0f}% da parcela de ações "
            f"(até R$ {politica.limite_por_acao * parcela_acoes_alvo:.2f} em {ticker})."
        )

    no_setor = sum((v for s, v in posicoes.values() if s == setor), ZERO)
    teto_setor = politica.limite_por_setor * parcela_acoes_alvo - no_setor
    if valor > teto_setor:
        valor = max(ZERO, teto_setor)
        motivos.append(f"Limite do setor {setor}: {politica.limite_por_setor * 100:.0f}% da parcela de ações.")

    perda_max = RISCO_MAX_POR_OPERACAO * patrimonio_investido
    perda = valor * risco_pct / 100
    if perda > perda_max:
        valor = perda_max * 100 / risco_pct
        motivos.append(
            f"Perda até o stop limitada a {RISCO_MAX_POR_OPERACAO * 100:.0f}% do patrimônio "
            f"(R$ {perda_max:.2f})."
        )

    valor = valor.quantize(Decimal("0.01"))
    if valor < VALOR_MINIMO:
        return Parecer(Veredito.VETADO, ZERO, tuple(motivos) or ("Valor muito pequeno.",))
    if valor < original:
        return Parecer(Veredito.AJUSTADO, valor, tuple(motivos))
    return Parecer(Veredito.APROVADO, valor, ("Dentro dos limites da política.",))
