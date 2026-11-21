from datetime import date
from decimal import Decimal as D

import pytest

from inventidor.dados import bcb
from inventidor.dados.cotacoes import parse_yahoo
from inventidor.dados.cvm import parse_ipe
from inventidor.dados.http import RedeIndisponivel, baixar
from inventidor.especialistas.noticias import Prioridade, alertas
from inventidor.especialistas.quant import MAX_DIAS, backtest, resumir, simular_trade
from inventidor.especialistas.tecnico import Candle, ler_precos


def cd(i, c, h=None, l=None):
    return Candle(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), D(str(c)),
                  D(str(h if h is not None else c)), D(str(l if l is not None else c)))


# --- fontes de dados (formato montado à mão, conforme a documentação das fontes) ---

def test_bcb_parse_e_ipca_composto():
    itens = [{"data": f"01/{m:02d}/2026", "valor": "1.00"} for m in range(1, 13)]
    serie = bcb.parse_serie(itens)
    assert serie[0][0] == date(2026, 1, 1)
    assert round(bcb.ipca_12_meses(serie), 2) == D("12.68")  # 1,01^12 - 1
    assert round(bcb.juro_real(D("15"), D("5")), 2) == D("9.52")


def test_yahoo_ignora_dias_sem_negociacao():
    resp = {"chart": {"result": [{
        "timestamp": [1766000000, 1766086400, 1766172800],
        "indicators": {"quote": [{"close": [10.123, None, 10.5], "high": [10.3, None, 10.7],
                                  "low": [10.0, None, 10.4]}]}}], "error": None}}
    candles = parse_yahoo(resp)
    assert len(candles) == 2
    assert candles[0].fechamento == D("10.12")


def test_yahoo_erro_explicito():
    with pytest.raises(ValueError):
        parse_yahoo({"chart": {"result": None, "error": {"code": "Not Found"}}})


IPE = (
    "CNPJ_Companhia;Nome_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;Especie;Assunto;"
    "Data_Entrega;Link_Download\n"
    "00.000.000/0001-00;PETROLEO BRASILEIRO S.A. PETROBRAS;1;2026-11-10;Fato Relevante;;;"
    "Aprovação de dividendos intercalares;2026-11-10;http://x/1\n"
    "00.000.000/0001-00;PETROLEO BRASILEIRO S.A. PETROBRAS;1;2026-11-11;Comunicado ao Mercado;;;"
    "Agenda corporativa;2026-11-11;http://x/2\n"
    "11.111.111/0001-11;OUTRA EMPRESA S.A.;2;2026-11-10;Fato Relevante;;;Algo;2026-11-10;http://x/3\n"
    "00.000.000/0001-00;PETROLEO BRASILEIRO S.A. PETROBRAS;1;2026-10-01;Reunião da Administração;;;"
    "Ata;2026-10-01;http://x/4\n"
)


def test_ipe_e_alertas_por_empresa_acompanhada():
    docs = parse_ipe(IPE)
    assert len(docs) == 4
    lista = alertas(docs, {"PETR4": "petroleo brasileiro"})
    assert [a.documento.link for a in lista] == ["http://x/1", "http://x/2"]  # outra empresa e ata fora
    assert lista[0].prioridade == Prioridade.ALTA and "provento" in lista[0].motivo
    assert lista[1].prioridade == Prioridade.MEDIA
    assert alertas(docs, {"PETR4": "petroleo brasileiro"}, desde=date(2026, 11, 11))[0].documento.link == "http://x/2"


def test_ipe_com_coluna_faltando_falha_claro():
    with pytest.raises(ValueError, match="Coluna ausente"):
        parse_ipe("A;B\n1;2\n")


def test_baixar_sem_rede_levanta_erro_claro(tmp_path, monkeypatch):
    import urllib.request, urllib.error

    def falha(*a, **k):
        raise urllib.error.URLError("bloqueado")

    monkeypatch.setattr(urllib.request, "urlopen", falha)
    with pytest.raises(RedeIndisponivel, match="exemplo.invalid"):
        baixar("https://exemplo.invalid/x", cache=tmp_path)


# --- backtest ---

def test_trade_sai_no_stop_antes_do_alvo_no_mesmo_dia():
    candles = [cd(0, 10, 10.2, 9.9), cd(1, 10, 12, 8)]  # dia 1 toca stop e alvo
    t = simular_trade("X", candles, 0, D(10), D(9), D(11))
    assert t.motivo == "stop" and t.saida == D(9)
    assert t.retorno_pct == D(-10)


def test_trade_alvo_e_prazo():
    candles = [cd(0, 10, 10.2, 9.9), cd(1, 10.5, 11.2, 10.4)]
    assert simular_trade("X", candles, 0, D(10), D(9), D(11)).motivo == "alvo"
    longo = [cd(0, 10, 10.1, 9.9)] + [cd(i, 10, 10.2, 9.8) for i in range(1, MAX_DIAS + 5)]
    t = simular_trade("X", longo, 0, D(10), D(9), D(11))
    assert t.motivo == "prazo" and t.saida == D(10)


def test_ordem_limitada_nao_executa_se_preco_nao_chega():
    assert simular_trade("X", [cd(0, 11, 11.5, 10.8)], 0, D(10), D(9), D(12)) is None


def test_backtest_nos_exemplos_e_consistente():
    series = ler_precos("exemplos/precos.csv")
    for t, candles in series.items():
        trades = backtest(t, candles)
        r = resumir(t, candles, trades)
        assert r.operacoes == len(trades)
        for tr in trades:
            assert tr.saida_data >= tr.entrada_data
        # posições não se sobrepõem
        for a, b in zip(trades, trades[1:]):
            assert b.entrada_data > a.saida_data
        assert 0 <= r.perda_maxima_pct < 100
