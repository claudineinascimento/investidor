from datetime import date
from decimal import Decimal as D

import pytest

from inventidor import diario
from inventidor.carteira import Carteira
from inventidor.diario import ErroDiario, Estado, Item
from inventidor.especialistas.mesa import boleta
from inventidor.importador import ler_csv


def item(id="20261121-BETA4", qtd=12):
    return Item(id=id, data=date(2026, 11, 21), ticker="BETA4", tipo="ACAO", quantidade=qtd,
                preco_limite=D("31.50"), stop=D("29.98"), alvo=D("34.54"), tese="ROE alto",
                parecer_risco="APROVADO: ok")


def test_fluxo_completo_e_estados(tmp_path):
    cam, ops = tmp_path / "d.jsonl", tmp_path / "ops.csv"
    assert diario.registrar_sugestao(item(), cam)
    assert not diario.registrar_sugestao(item(), cam)  # idempotente
    assert diario.carregar(cam)["20261121-BETA4"].estado == Estado.SUGERIDA
    diario.aprovar("20261121-BETA4", cam)
    diario.executar("20261121-BETA4", D("31.40"), custos=D("1.20"), dia=date(2026, 11, 21),
                    operacoes_csv=ops, caminho=cam)
    assert diario.carregar(cam)["20261121-BETA4"].estado == Estado.EXECUTADA
    carteira = Carteira().processar(ler_csv(ops))
    pos = carteira.posicoes["BETA4"]
    assert pos.quantidade == 12 and pos.custo_total == D("12") * D("31.40") + D("1.20")


def test_nao_executa_nem_gera_boleta_sem_aprovacao(tmp_path):
    cam = tmp_path / "d.jsonl"
    diario.registrar_sugestao(item(), cam)
    with pytest.raises(ErroDiario):
        diario.executar("20261121-BETA4", D("31.50"), caminho=cam)
    with pytest.raises(ErroDiario):
        boleta(diario.carregar(cam)["20261121-BETA4"])


def test_recusada_nao_pode_ser_aprovada_nem_executada(tmp_path):
    cam = tmp_path / "d.jsonl"
    diario.registrar_sugestao(item(), cam)
    diario.recusar("20261121-BETA4", "mudei de ideia", cam)
    with pytest.raises(ErroDiario):
        diario.aprovar("20261121-BETA4", cam)
    with pytest.raises(ErroDiario):
        diario.executar("20261121-BETA4", D("31.50"), caminho=cam)


def test_preco_muito_acima_do_limite_e_barrado(tmp_path):
    cam = tmp_path / "d.jsonl"
    diario.registrar_sugestao(item(), cam)
    diario.aprovar("20261121-BETA4", cam)
    with pytest.raises(ErroDiario, match="2% acima"):
        diario.executar("20261121-BETA4", D("33"), caminho=cam)


def test_id_inexistente(tmp_path):
    with pytest.raises(ErroDiario, match="não existe"):
        diario.aprovar("nada", tmp_path / "d.jsonl")


def test_boleta_fracionario_e_limitada(tmp_path):
    cam = tmp_path / "d.jsonl"
    diario.registrar_sugestao(item(), cam)
    diario.aprovar("20261121-BETA4", cam)
    texto = boleta(diario.carregar(cam)["20261121-BETA4"])
    assert "BETA4F" in texto and "ORDEM LIMITADA" in texto and "31.50" in texto
    assert "BETA4F" not in boleta(Item(**{**item(qtd=100).__dict__, "estado": Estado.APROVADA}))
