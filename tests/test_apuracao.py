from datetime import date
from decimal import Decimal as D

import pytest

from inventidor.carteira import Carteira, VendaSemPosicao
from inventidor.impostos.apuracao import apurar_periodo, vencimento_darf
from inventidor.importador import ler_csv
from inventidor.modelos import Lado, Modalidade, Operacao, TipoAtivo


def op(dia, ticker, lado, qtd, preco, tipo=TipoAtivo.ACAO, custos="0", irrf="0"):
    return Operacao(dia, ticker, tipo, Lado(lado), qtd, D(str(preco)), D(custos), D(irrf))


def apurar(*ops):
    return apurar_periodo(Carteira().processar(ops))


def test_preco_medio_inclui_custos():
    c = Carteira().processar([
        op(date(2026, 1, 5), "ITSA4", "C", 100, 10, custos="5"),
        op(date(2026, 1, 6), "ITSA4", "C", 100, 12, custos="5"),
    ])
    assert c.posicoes["ITSA4"].preco_medio == D("11.05")


def test_vendas_ate_20_mil_sao_isentas():
    (ap,) = apurar(
        op(date(2026, 1, 5), "PETR4", "C", 100, 30),
        op(date(2026, 2, 5), "PETR4", "V", 100, 35),
    )
    assert ap.isencao_aplicada
    assert ap.imposto_a_pagar == 0


def test_lucro_comum_tributado_a_15_menos_irrf():
    (ap,) = apurar(
        op(date(2026, 1, 5), "VALE3", "C", 1000, 60),
        op(date(2026, 2, 5), "VALE3", "V", 500, 70, irrf="1.75"),
    )
    assert not ap.isencao_aplicada
    assert ap.imposto_a_pagar == D("748.25")  # 5000 x 15% - 1,75
    assert ap.vencimento == date(2026, 3, 31)


def test_prejuizo_compensa_lucro_do_mes_seguinte():
    ap1, ap2 = apurar(
        op(date(2026, 1, 5), "VALE3", "C", 1000, 60),
        op(date(2026, 2, 5), "VALE3", "V", 500, 50),  # prejuízo 5.000
        op(date(2026, 3, 5), "VALE3", "V", 500, 80),  # lucro 10.000
    )
    assert ap1.saldos_finais.prejuizo[Modalidade.COMUM] == D("5000")
    assert ap2.imposto_a_pagar == D("750.00")  # (10.000 - 5.000) x 15%
    assert ap2.saldos_finais.prejuizo[Modalidade.COMUM] == 0


def test_day_trade_20_porcento_sem_isencao():
    (ap,) = apurar(
        op(date(2026, 1, 5), "BBAS3", "C", 100, 10),
        op(date(2026, 1, 5), "BBAS3", "V", 100, 11, irrf="1"),
    )
    linha = next(l for l in ap.linhas if l.modalidade == Modalidade.DAY_TRADE)
    assert linha.imposto == D("20.00")
    assert ap.imposto_a_pagar == D("19.00")


def test_day_trade_parcial_separa_operacao_comum():
    (ap,) = apurar(
        op(date(2026, 1, 2), "BBAS3", "C", 100, 10),
        op(date(2026, 1, 5), "BBAS3", "C", 50, 12),
        op(date(2026, 1, 5), "BBAS3", "V", 150, 13),
    )
    por_mod = {l.modalidade: l for l in ap.linhas}
    assert por_mod[Modalidade.DAY_TRADE].resultado_mes == D("50.00")  # 50 x (13 - 12)
    assert por_mod[Modalidade.COMUM].resultado_mes == D("300.00")  # 100 x (13 - 10), isento
    assert por_mod[Modalidade.COMUM].isento == D("300.00")


def test_darf_abaixo_de_10_reais_acumula():
    ap1, ap2 = apurar(
        op(date(2026, 1, 5), "BBAS3", "C", 100, 10),
        op(date(2026, 1, 5), "BBAS3", "V", 100, D("10.30")),
        op(date(2026, 2, 5), "BBAS3", "C", 100, 10),
        op(date(2026, 2, 5), "BBAS3", "V", 100, D("10.30")),
    )
    assert ap1.imposto_a_pagar == 0
    assert ap1.saldos_finais.imposto_abaixo_minimo == D("6.00")
    assert ap2.imposto_a_pagar == D("12.00")


def test_fii_20_porcento_sem_isencao():
    (ap,) = apurar(
        op(date(2026, 1, 5), "MXRF11", "C", 100, 100, tipo=TipoAtivo.FII),
        op(date(2026, 2, 5), "MXRF11", "V", 100, 110, tipo=TipoAtivo.FII),
    )
    assert ap.imposto_a_pagar == D("200.00")


def test_etf_nao_tem_isencao():
    (ap,) = apurar(
        op(date(2026, 1, 5), "BOVA11", "C", 100, 100, tipo=TipoAtivo.ETF),
        op(date(2026, 2, 5), "BOVA11", "V", 100, 110, tipo=TipoAtivo.ETF),
    )
    assert ap.imposto_a_pagar == D("150.00")


def test_venda_sem_posicao_e_bloqueada():
    with pytest.raises(VendaSemPosicao):
        Carteira().processar([op(date(2026, 1, 5), "WEGE3", "V", 10, 40)])


def test_vencimento_ultimo_dia_util_do_mes_seguinte():
    assert vencimento_darf(2026, 10) == date(2026, 11, 30)
    assert vencimento_darf(2026, 12) == date(2027, 1, 29)


def test_importa_exemplo_com_virgula_decimal():
    ops = ler_csv("exemplos/operacoes.csv")
    assert len(ops) == 8
    assert ops[0].custos == D("12.50")
    aps = apurar_periodo(Carteira().processar(ops))
    assert [(a.ano, a.mes) for a in aps] == [(2026, 9), (2026, 10), (2026, 11)]
