"""Apuração mensal do IR sobre renda variável (o trabalho do agente Contador).

Todo cálculo é feito aqui, em código determinístico. O agente de IA só
chama estas funções e explica o resultado; ele nunca calcula imposto "de cabeça".
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from inventidor.carteira import Carteira
from inventidor.impostos.regras import RegrasIR, regras_vigentes
from inventidor.modelos import Modalidade, ResultadoVenda, Saldos, TipoAtivo

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")


def _r(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def vencimento_darf(ano: int, mes: int) -> date:
    """Último dia útil do mês seguinte ao da apuração.

    Considera só fins de semana; feriados nacionais ainda não são tratados.
    """
    ano_v, mes_v = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    dia = date(ano_v, mes_v, calendar.monthrange(ano_v, mes_v)[1])
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return dia


@dataclass
class LinhaModalidade:
    modalidade: Modalidade
    resultado_mes: Decimal
    isento: Decimal  # lucro de ações isento (vendas até o limite)
    prejuizo_anterior: Decimal
    base_calculo: Decimal
    aliquota: Decimal
    imposto: Decimal
    prejuizo_a_compensar: Decimal


@dataclass
class ApuracaoMensal:
    ano: int
    mes: int
    vendas_acoes: Decimal
    isencao_aplicada: bool
    linhas: list[LinhaModalidade]
    imposto_bruto: Decimal
    irrf_deduzido: Decimal
    imposto_acumulado_anterior: Decimal
    imposto_a_pagar: Decimal  # valor do DARF deste mês (0 se abaixo do mínimo)
    vencimento: date | None
    codigo_darf: str
    saldos_finais: Saldos
    avisos: list[str] = field(default_factory=list)

    @property
    def competencia(self) -> str:
        return f"{self.mes:02d}/{self.ano}"


def apurar_mes(
    ano: int,
    mes: int,
    resultados: list[ResultadoVenda],
    saldos: Saldos | None = None,
    regras: RegrasIR | None = None,
) -> ApuracaoMensal:
    regras = regras or regras_vigentes(date(ano, mes, 1))
    anteriores = saldos or Saldos()
    novos = Saldos(
        prejuizo=dict(anteriores.prejuizo),
        irrf_a_compensar=anteriores.irrf_a_compensar,
        imposto_abaixo_minimo=anteriores.imposto_abaixo_minimo,
    )
    avisos: list[str] = []

    acoes_comuns = [
        r for r in resultados if r.modalidade == Modalidade.COMUM and r.tipo == TipoAtivo.ACAO
    ]
    vendas_acoes = sum((r.valor_alienacao for r in acoes_comuns), ZERO)
    isento_mes = vendas_acoes <= regras.limite_isencao_acoes

    linhas: list[LinhaModalidade] = []
    imposto_bruto = ZERO
    for mod in Modalidade:
        do_grupo = [r for r in resultados if r.modalidade == mod]
        resultado = sum((r.resultado for r in do_grupo), ZERO)
        isento = ZERO

        if mod == Modalidade.COMUM and isento_mes:
            res_acoes = sum((r.resultado for r in acoes_comuns), ZERO)
            if res_acoes > 0:
                isento = res_acoes
            elif res_acoes < 0 and not regras.compensar_prejuizo_mes_isento:
                isento = res_acoes  # prejuízo descartado
            resultado_tributavel = resultado - isento
        else:
            resultado_tributavel = resultado

        prejuizo_ant = anteriores.prejuizo[mod]
        base = resultado_tributavel - prejuizo_ant if resultado_tributavel > 0 else ZERO
        if resultado_tributavel > 0:
            if base > 0:
                novos.prejuizo[mod] = ZERO
            else:
                novos.prejuizo[mod] = -base
                base = ZERO
        else:
            novos.prejuizo[mod] = prejuizo_ant - resultado_tributavel

        imposto = _r(base * regras.aliquota[mod])
        imposto_bruto += imposto
        linhas.append(
            LinhaModalidade(
                modalidade=mod,
                resultado_mes=_r(resultado),
                isento=_r(isento),
                prejuizo_anterior=_r(prejuizo_ant),
                base_calculo=_r(base),
                aliquota=regras.aliquota[mod],
                imposto=imposto,
                prejuizo_a_compensar=_r(novos.prejuizo[mod]),
            )
        )

    irrf_disponivel = anteriores.irrf_a_compensar + sum((r.irrf for r in resultados), ZERO)
    irrf_deduzido = min(irrf_disponivel, imposto_bruto)
    novos.irrf_a_compensar = _r(irrf_disponivel - irrf_deduzido)

    devido = imposto_bruto - irrf_deduzido + anteriores.imposto_abaixo_minimo
    if devido >= regras.darf_minimo:
        a_pagar = _r(devido)
        novos.imposto_abaixo_minimo = ZERO
        venc = vencimento_darf(ano, mes)
        avisos.append(
            f"Pagar DARF código {regras.codigo_darf} de R$ {a_pagar} até {venc:%d/%m/%Y} "
            "(confira feriados)."
        )
    else:
        a_pagar = ZERO
        novos.imposto_abaixo_minimo = _r(devido)
        venc = None
        if devido > 0:
            avisos.append(
                f"Imposto de R$ {_r(devido)} abaixo do mínimo de R$ {regras.darf_minimo}: "
                "acumula para o próximo mês."
            )

    if isento_mes and acoes_comuns:
        avisos.append(
            f"Vendas de ações no mês: R$ {_r(vendas_acoes)} (até R$ {regras.limite_isencao_acoes}): "
            "lucro isento, mas deve ser declarado no IR anual."
        )

    return ApuracaoMensal(
        ano=ano,
        mes=mes,
        vendas_acoes=_r(vendas_acoes),
        isencao_aplicada=isento_mes and bool(acoes_comuns),
        linhas=linhas,
        imposto_bruto=imposto_bruto,
        irrf_deduzido=_r(irrf_deduzido),
        imposto_acumulado_anterior=anteriores.imposto_abaixo_minimo,
        imposto_a_pagar=a_pagar,
        vencimento=venc,
        codigo_darf=regras.codigo_darf,
        saldos_finais=novos,
        avisos=avisos,
    )


def apurar_periodo(carteira: Carteira, saldos: Saldos | None = None) -> list[ApuracaoMensal]:
    """Apura todos os meses com vendas, levando saldos de um mês para o outro.

    Meses sem venda não geram apuração, mas os saldos continuam valendo.
    """
    saldos = saldos or Saldos()
    saida: list[ApuracaoMensal] = []
    for (ano, mes), resultados in carteira.resultados_por_mes().items():
        ap = apurar_mes(ano, mes, resultados, saldos)
        saldos = ap.saldos_finais
        saida.append(ap)
    return saida
