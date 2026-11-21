from decimal import Decimal as D

from inventidor.especialistas.consultor import (
    Classe, Perfil, PerfilRisco, definir_politica, distribuir_valor, plano_aportes,
)
from inventidor.especialistas.fundamentalista import Fundamentos, avaliar, ler_fundamentos
from inventidor.especialistas.orquestrador import plano_do_mes
from inventidor.especialistas.risco import Veredito, avaliar_compra
from inventidor.especialistas.tecnico import Sinal, analisar, ler_precos


def perfil(**kw):
    base = dict(valor_disponivel=D(10000), aporte_mensal=D(500), gastos_mensais=D(3000),
                reserva_atual=D(18000), prazo_anos=10, perfil_risco=PerfilRisco.MODERADO)
    base.update(kw)
    return Perfil(**base)


def test_politica_moderada_soma_100():
    pol = definir_politica(perfil())
    assert sum(pol.alocacao.values()) == 1
    assert pol.alocacao[Classe.ACOES] == D("0.20")
    assert pol.falta_reserva == 0


def test_sem_reserva_dinheiro_vai_primeiro_para_reserva():
    pol = definir_politica(perfil(reserva_atual=D(0)))
    dist = distribuir_valor(pol, D(10000))
    assert dist[Classe.RESERVA] == D(10000)
    assert dist[Classe.ACOES] == 0


def test_prazo_curto_limita_renda_variavel():
    assert definir_politica(perfil(prazo_anos=1)).pct_renda_variavel == 0
    assert definir_politica(perfil(prazo_anos=3)).pct_renda_variavel <= D("0.20")


def test_aporte_compra_o_que_esta_abaixo_do_alvo():
    pol = definir_politica(perfil())
    atual = {Classe.RENDA_FIXA: D(6000), Classe.ACOES: D(1000), Classe.FIIS: D(1500), Classe.ETF: D(1500)}
    dist = distribuir_valor(pol, D(500), atual)
    # alvo após o aporte: ações 2.100 (faltam 1.100), FIIs e ETF 1.575 (faltam 75 cada)
    assert dist[Classe.ACOES] == D(440)
    assert dist[Classe.FIIS] == dist[Classe.ETF] == D(30)
    assert dist[Classe.RENDA_FIXA] == 0
    assert sum(dist.values()) == D(500)


def test_plano_de_aportes_acumula_sem_rentabilidade():
    plano = plano_aportes(definir_politica(perfil()), meses=12)
    assert len(plano) == 13
    assert sum(plano[-1].acumulado.values()) == D(16000)


def emp(**kw):
    base = dict(ticker="TEST3", setor="X", preco=D(20), lpa=D(2), vpa=D(10), dpa=D("1.4"),
                roe=D(20), margem_liquida=D(15), div_liq_ebitda=D("0.5"),
                cresc_lucro_5a=D(10), liquidez_diaria=D(50_000_000))
    base.update(kw)
    return Fundamentos(**base)


def test_fundamentalista_elimina_prejuizo_e_divida_alta():
    assert not avaliar(emp(lpa=D(-1))).aprovada
    assert not avaliar(emp(div_liq_ebitda=D(4))).aprovada
    assert not avaliar(emp(liquidez_diaria=D(100_000))).aprovada


def test_preco_justo_graham_e_bazin():
    av = avaliar(emp())
    assert av.preco_graham == D("21.21")  # raiz(22,5 x 2 x 10)
    assert av.preco_bazin == D("23.33")  # 1,40 / 6%
    assert av.margem_seguranca > 0


def test_tecnico_nos_exemplos():
    precos = ler_precos("exemplos/precos.csv")
    assert analisar("DELT3", precos["DELT3"]).sinal == Sinal.EVITAR
    assert analisar("ZETA3", precos["ZETA3"]).sinal == Sinal.AGUARDAR
    beta = analisar("BETA4", precos["BETA4"])
    assert beta.sinal == Sinal.COMPRAR
    assert beta.stop < beta.entrada_min <= beta.entrada_max < beta.alvo


def _risco(**kw):
    base = dict(ticker="AAA3", setor="Energia", valor=D(400), risco_pct=D(5),
                politica=definir_politica(perfil()), parcela_acoes_alvo=D(2000),
                patrimonio_investido=D(10000), posicoes={})
    base.update(kw)
    return avaliar_compra(**base)


def test_risco_aprova_dentro_dos_limites():
    assert _risco().veredito == Veredito.APROVADO


def test_risco_veta_stop_distante():
    assert _risco(risco_pct=D(20)).veredito == Veredito.VETADO


def test_risco_ajusta_concentracao_no_setor():
    p = _risco(posicoes={"BBB3": ("Energia", D(600))})
    assert p.veredito == Veredito.AJUSTADO
    assert p.valor == D(200)  # 40% x 2.000 - 600


def test_plano_do_mes_respeita_limites():
    pol = definir_politica(perfil())
    plano = plano_do_mes(pol, D(10000), ler_fundamentos("exemplos/fundamentos.csv"),
                         ler_precos("exemplos/precos.csv"))
    tickers = [s.ticker for s in plano.sugestoes]
    assert "BETA4" in tickers
    assert "EPSI3" not in tickers and "DELT3" not in tickers and "GAMA3" not in tickers
    assert all(s.valor <= D(400) for s in plano.sugestoes)
    energia = sum(s.valor for s in plano.sugestoes if s.setor == "Energia elétrica")
    assert energia <= D(800)
    assert sum(s.valor for s in plano.sugestoes) + plano.sobra_acoes == D(2000)
