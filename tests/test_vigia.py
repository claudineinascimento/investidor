from datetime import date
from decimal import Decimal as D

from inventidor import diario
from inventidor.diario import Item
from inventidor.especialistas.mesa import boleta
from inventidor.especialistas.tecnico import Candle
from inventidor.especialistas.vigia import Gatilho, itens_de_venda, vigiar
from inventidor.importador import ler_csv

HOJE = date(2026, 11, 21)


def montar(tmp_path):
    cam, ops = tmp_path / "d.jsonl", tmp_path / "ops.csv"
    it = Item(id="20261101-BETA4", data=date(2026, 11, 1), ticker="BETA4", tipo="ACAO", quantidade=100,
              preco_limite=D("30"), stop=D("28"), alvo=D("36"), tese="t", parecer_risco="ok")
    diario.registrar_sugestao(it, cam)
    diario.aprovar(it.id, cam)
    diario.executar(it.id, D("30"), dia=date(2026, 11, 1), operacoes_csv=ops, caminho=cam)
    return cam, ops


def candle(c, h, l):
    return [Candle(HOJE, D(c), D(h), D(l))]


def test_stop_atingido_vende_tudo(tmp_path):
    cam, ops = montar(tmp_path)
    (s,) = vigiar(ler_csv(ops), {"BETA4": candle("27.8", "29", "27.5")}, diario.carregar(cam), HOJE)
    assert s.gatilho == Gatilho.STOP and s.quantidade == 100
    assert s.resultado_estimado < 0 and s.imposto_adicional == 0


def test_alvo_vende_metade_e_estima_imposto(tmp_path):
    cam, ops = montar(tmp_path)
    (s,) = vigiar(ler_csv(ops), {"BETA4": candle("36.5", "37", "35")}, diario.carregar(cam), HOJE)
    assert s.gatilho == Gatilho.ALVO and s.quantidade == 50
    # 50 x 36,32 = R$ 1.816 de vendas: isento (até R$ 20 mil no mês)
    assert s.resultado_estimado > 0 and s.imposto_adicional == 0


def test_alvo_acima_do_limite_de_isencao_gera_imposto(tmp_path):
    cam, ops = montar(tmp_path)
    ops.write_text(ops.read_text().replace(";100;30;", ";1000;30;"))  # 1.000 ações em carteira
    (s,) = vigiar(ler_csv(ops), {"BETA4": candle("41", "42", "40")}, diario.carregar(cam), HOJE)
    # 500 x 40,79 = R$ 20.395 > R$ 20 mil: perde a isenção, lucro de ~R$ 5.397 a 15%
    assert s.quantidade == 500 and D("800") < s.imposto_adicional < D("820")


def test_sem_gatilho_ou_sem_stop_nada_acontece(tmp_path):
    cam, ops = montar(tmp_path)
    assert vigiar(ler_csv(ops), {"BETA4": candle("32", "33", "31")}, diario.carregar(cam), HOJE) == []
    assert vigiar(ler_csv(ops), {"BETA4": candle("20", "21", "19")}, {}, HOJE) == []  # sem níveis registrados


def test_venda_entra_na_fila_e_na_carteira(tmp_path):
    cam, ops = montar(tmp_path)
    sinais = vigiar(ler_csv(ops), {"BETA4": candle("27.8", "29", "27.5")}, diario.carregar(cam), HOJE)
    (v,) = itens_de_venda(sinais, HOJE)
    assert v.lado == "V" and v.id == "20261121-V-BETA4"
    diario.registrar_sugestao(v, cam)
    diario.aprovar(v.id, cam)
    assert "VENDA" in boleta(diario.carregar(cam)[v.id])
    diario.executar(v.id, D("27.7"), dia=HOJE, operacoes_csv=ops, caminho=cam)
    from inventidor.carteira import Carteira
    assert Carteira().processar(ler_csv(ops)).posicoes_abertas() == []
