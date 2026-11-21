"""Consultor: perfil do investidor, política de investimento e plano de aportes.

As faixas de alocação abaixo são pontos de partida usuais de mercado para cada
perfil, não uma regra. O agente Consultor usa estas funções e explica o
resultado; ajuste os números em ALOCACAO_BASE se quiser outra referência.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import Enum

ZERO = Decimal("0")


class PerfilRisco(str, Enum):
    CONSERVADOR = "conservador"
    MODERADO = "moderado"
    ARROJADO = "arrojado"


class Classe(str, Enum):
    RESERVA = "Reserva de emergência"
    RENDA_FIXA = "Renda fixa"
    ACOES = "Ações"
    FIIS = "FIIs"
    ETF = "ETF de índice"


RENDA_VARIAVEL = (Classe.ACOES, Classe.FIIS, Classe.ETF)

# % do patrimônio investível (depois da reserva) por classe.
ALOCACAO_BASE: dict[PerfilRisco, dict[Classe, Decimal]] = {
    PerfilRisco.CONSERVADOR: {
        Classe.RENDA_FIXA: Decimal("0.70"),
        Classe.ACOES: Decimal("0.10"),
        Classe.FIIS: Decimal("0.10"),
        Classe.ETF: Decimal("0.10"),
    },
    PerfilRisco.MODERADO: {
        Classe.RENDA_FIXA: Decimal("0.50"),
        Classe.ACOES: Decimal("0.20"),
        Classe.FIIS: Decimal("0.15"),
        Classe.ETF: Decimal("0.15"),
    },
    PerfilRisco.ARROJADO: {
        Classe.RENDA_FIXA: Decimal("0.30"),
        Classe.ACOES: Decimal("0.35"),
        Classe.FIIS: Decimal("0.15"),
        Classe.ETF: Decimal("0.20"),
    },
}

# Limites usados pelo Gestor de Risco, em % da parcela de ações.
LIMITE_POR_ACAO = {
    PerfilRisco.CONSERVADOR: Decimal("0.20"),
    PerfilRisco.MODERADO: Decimal("0.20"),
    PerfilRisco.ARROJADO: Decimal("0.25"),
}
LIMITE_POR_SETOR = Decimal("0.40")
# Queda da renda variável no mês que dispara alerta de revisão.
ALERTA_PERDA_MENSAL = {
    PerfilRisco.CONSERVADOR: Decimal("0.05"),
    PerfilRisco.MODERADO: Decimal("0.08"),
    PerfilRisco.ARROJADO: Decimal("0.12"),
}
MESES_RESERVA = 6


@dataclass(frozen=True)
class Perfil:
    valor_disponivel: Decimal  # quanto quer investir agora
    aporte_mensal: Decimal
    gastos_mensais: Decimal
    reserva_atual: Decimal  # reserva de emergência que já existe, fora deste valor
    prazo_anos: int
    perfil_risco: PerfilRisco


@dataclass(frozen=True)
class Politica:
    perfil: Perfil
    alocacao: dict[Classe, Decimal]  # % do patrimônio investível
    falta_reserva: Decimal
    limite_por_acao: Decimal
    limite_por_setor: Decimal
    alerta_perda_mensal: Decimal
    observacoes: tuple[str, ...]

    @property
    def pct_renda_variavel(self) -> Decimal:
        return sum((self.alocacao[c] for c in RENDA_VARIAVEL), ZERO)


def definir_politica(perfil: Perfil) -> Politica:
    obs: list[str] = []
    alocacao = dict(ALOCACAO_BASE[perfil.perfil_risco])

    meta_reserva = perfil.gastos_mensais * MESES_RESERVA
    falta_reserva = max(ZERO, meta_reserva - perfil.reserva_atual)
    if falta_reserva:
        obs.append(
            f"Antes da bolsa, complete a reserva de emergência: faltam R$ {falta_reserva:.2f} "
            f"para {MESES_RESERVA} meses de gastos. Ela fica em renda fixa com liquidez diária."
        )

    # Prazo curto não combina com bolsa: limita a renda variável.
    if perfil.prazo_anos < 2:
        teto_rv = ZERO
        obs.append("Prazo abaixo de 2 anos: tudo em renda fixa. Bolsa pede pelo menos 5 anos.")
    elif perfil.prazo_anos < 5:
        teto_rv = Decimal("0.20")
        obs.append("Prazo de 2 a 5 anos: renda variável limitada a 20%.")
    else:
        teto_rv = Decimal("1")

    rv = sum((alocacao[c] for c in RENDA_VARIAVEL), ZERO)
    if rv > teto_rv:
        fator = teto_rv / rv
        for c in RENDA_VARIAVEL:
            alocacao[c] = (alocacao[c] * fator).quantize(Decimal("0.0001"))
        alocacao[Classe.RENDA_FIXA] = Decimal("1") - sum(
            (alocacao[c] for c in RENDA_VARIAVEL), ZERO
        )

    if perfil.valor_disponivel <= Decimal("20000"):
        obs.append(
            "Com valores até R$ 20 mil, use o mercado fracionário (ticker com F no final, "
            "ex.: ITSA4F) para comprar menos de 100 ações e diversificar desde o início."
        )

    return Politica(
        perfil=perfil,
        alocacao=alocacao,
        falta_reserva=falta_reserva,
        limite_por_acao=LIMITE_POR_ACAO[perfil.perfil_risco],
        limite_por_setor=LIMITE_POR_SETOR,
        alerta_perda_mensal=ALERTA_PERDA_MENSAL[perfil.perfil_risco],
        observacoes=tuple(obs),
    )


def _centavos(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def distribuir_valor(
    politica: Politica, valor: Decimal, atual: dict[Classe, Decimal] | None = None
) -> dict[Classe, Decimal]:
    """Divide um valor (inicial ou aporte) entre as classes.

    Primeiro completa a reserva. Depois compra o que está abaixo do alvo
    (rebalanceamento só com aportes, sem vender e sem gerar imposto).
    """
    atual = dict(atual or {})
    saida = {c: ZERO for c in Classe}
    restante = valor

    falta = max(ZERO, politica.falta_reserva - atual.get(Classe.RESERVA, ZERO))
    if falta:
        usar = min(falta, restante)
        saida[Classe.RESERVA] = _centavos(usar)
        restante -= saida[Classe.RESERVA]
    if restante <= 0:
        return saida

    investido = sum((atual.get(c, ZERO) for c in politica.alocacao), ZERO)
    total_depois = investido + restante
    deficits = {
        c: max(ZERO, total_depois * pct - atual.get(c, ZERO))
        for c, pct in politica.alocacao.items()
    }
    soma = sum(deficits.values(), ZERO)
    if soma == 0:
        return saida
    for c, d in deficits.items():
        saida[c] = _centavos(restante * d / soma)
    # Centavos que sobraram do arredondamento vão para a renda fixa.
    saida[Classe.RENDA_FIXA] += valor - sum(saida.values(), ZERO)
    return saida


@dataclass(frozen=True)
class MesPlano:
    mes: int
    aporte: dict[Classe, Decimal]
    acumulado: dict[Classe, Decimal]


def plano_aportes(politica: Politica, meses: int = 12) -> list[MesPlano]:
    """Valor inicial no mês 0 e um aporte por mês, sem supor rentabilidade."""
    p = politica.perfil
    acumulado = {c: ZERO for c in Classe}
    plano: list[MesPlano] = []
    for mes in range(meses + 1):
        valor = p.valor_disponivel if mes == 0 else p.aporte_mensal
        if valor <= 0:
            continue
        aporte = distribuir_valor(politica, valor, acumulado)
        for c, v in aporte.items():
            acumulado[c] += v
        plano.append(MesPlano(mes, aporte, dict(acumulado)))
    return plano
