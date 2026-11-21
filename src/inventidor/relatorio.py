"""Textos legíveis dos resultados, para o painel e para os agentes explicarem."""

from __future__ import annotations

from inventidor.carteira import Carteira
from inventidor.impostos.apuracao import ApuracaoMensal

NOMES = {"COMUM": "Operações comuns", "DAY_TRADE": "Day trade", "FII": "FIIs"}

AVISO_LEGAL = (
    "Apoio à decisão para uso pessoal. Não é recomendação de investimento nem "
    "substitui contador. Confira os valores antes de pagar ou declarar."
)


def texto_carteira(carteira: Carteira) -> str:
    linhas = ["Posições abertas", f"{'Ativo':<8} {'Qtd':>8} {'Preço médio':>14} {'Custo total':>14}"]
    for p in sorted(carteira.posicoes_abertas(), key=lambda p: p.ticker):
        linhas.append(
            f"{p.ticker:<8} {p.quantidade:>8} {p.preco_medio:>14.2f} {p.custo_total:>14.2f}"
        )
    return "\n".join(linhas)


def texto_apuracao(ap: ApuracaoMensal) -> str:
    linhas = [f"Apuração {ap.competencia}", f"Vendas de ações (operações comuns): R$ {ap.vendas_acoes}"]
    for l in ap.linhas:
        if not (l.resultado_mes or l.prejuizo_anterior or l.prejuizo_a_compensar):
            continue
        linhas.append(
            f"  {NOMES[l.modalidade.value]}: resultado R$ {l.resultado_mes}"
            + (f", isento R$ {l.isento}" if l.isento else "")
            + f", prejuízo anterior R$ {l.prejuizo_anterior}, base R$ {l.base_calculo}"
            + f", imposto R$ {l.imposto} ({l.aliquota * 100:.0f}%)"
            + f", prejuízo a compensar R$ {l.prejuizo_a_compensar}"
        )
    linhas.append(f"  IRRF deduzido: R$ {ap.irrf_deduzido}")
    linhas.append(f"  DARF a pagar: R$ {ap.imposto_a_pagar}")
    linhas.extend(f"  ! {a}" for a in ap.avisos)
    return "\n".join(linhas)
