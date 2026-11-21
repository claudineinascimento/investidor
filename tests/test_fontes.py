import json

import pytest

from inventidor.dados.fontes import Cadastro, ErroFonte, Fonte, FonteDesativada, PADRAO, validar


def cad(tmp_path):
    return Cadastro(list(PADRAO), tmp_path / "fontes.json")


def test_padrao_tem_as_tres_fontes_validas():
    assert sorted(f.host for f in PADRAO) == ["api.bcb.gov.br", "dados.cvm.gov.br", "query1.finance.yahoo.com"]
    for f in PADRAO:
        validar(f)
    assert PADRAO[0].url(serie=432, k=1).endswith("bcdata.sgs.432/dados/ultimos/1?formato=json")


def test_desativar_bloqueia_e_ativar_libera(tmp_path):
    c = cad(tmp_path)
    c.definir_ativa("bcb_sgs", False)
    with pytest.raises(FonteDesativada, match="macro"):
        c.da_vez("macro")
    assert "api.bcb.gov.br" not in c.hosts_ativos()
    c.definir_ativa("bcb_sgs", True)
    assert c.da_vez("macro").nome == "bcb_sgs"


def test_persiste_e_recarrega(tmp_path):
    c = cad(tmp_path)
    c.definir_ativa("yahoo_cotacoes", False)
    outro = Cadastro.carregar(tmp_path / "fontes.json")
    assert outro.fontes["yahoo_cotacoes"].ativa is False
    assert set(outro.fontes) == {"bcb_sgs", "yahoo_cotacoes", "cvm_ipe"}


def test_prioridade_escolhe_a_fonte_da_vez(tmp_path):
    c = cad(tmp_path)
    c.cadastrar(Fonte("yahoo_espelho", "cotacoes", "yahoo_chart",
                      "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}.SA?range={periodo}&interval=1d",
                      prioridade=1))
    assert c.da_vez("cotacoes").nome == "yahoo_espelho"
    c.definir_ativa("yahoo_espelho", False)
    assert c.da_vez("cotacoes").nome == "yahoo_cotacoes"


@pytest.mark.parametrize("campos,trecho", [
    (dict(url_modelo="http://api.bcb.gov.br/{serie}/{k}"), "https"),
    (dict(url_modelo="https://user:pw@api.bcb.gov.br/{serie}/{k}"), "usuário"),
    (dict(url_modelo="https://api.bcb.gov.br:8443/{serie}/{k}"), "porta"),
    (dict(url_modelo="https://api.bcb.gov.br/{serie}/{k}/{segredo}"), "não existem"),
    (dict(url_modelo="https://api.bcb.gov.br/{serie}"), "Faltam"),
    (dict(tipo="cotacoes"), "serve para o tipo macro"),
    (dict(formato="outro"), "desconhecido"),
    (dict(tipo="x"), "inválido"),
    (dict(nome="Nome Ruim"), "Nome"),
    (dict(ttl_segundos=-1), "negativo"),
])
def test_validacao_recusa_cadastro_perigoso_ou_errado(campos, trecho):
    base = dict(nome="minha", tipo="macro", formato="bcb_sgs",
                url_modelo="https://api.bcb.gov.br/dados/{serie}/{k}")
    with pytest.raises(ErroFonte, match=trecho):
        validar(Fonte(**{**base, **campos}))


def test_nao_substitui_sem_pedir(tmp_path):
    c = cad(tmp_path)
    with pytest.raises(ErroFonte, match="Já existe"):
        c.cadastrar(PADRAO[0])
    c.cadastrar(PADRAO[0], substituir=True)


def test_arquivo_corrompido_da_erro_claro(tmp_path):
    arq = tmp_path / "fontes.json"
    arq.write_text("{ nao e json")
    with pytest.raises(ErroFonte, match="inválido"):
        Cadastro.carregar(arq)
    arq.write_text(json.dumps({"fontes": [{"nome": "x"}]}))
    with pytest.raises(ErroFonte):
        Cadastro.carregar(arq)


def test_coletor_respeita_fonte_desativada(tmp_path, monkeypatch):
    c = cad(tmp_path)
    c.definir_ativa("cvm_ipe", False)
    monkeypatch.setenv("INVENTIDOR_FONTES", str(tmp_path / "fontes.json"))
    from inventidor.dados.cvm import baixar_ipe
    with pytest.raises(FonteDesativada):
        baixar_ipe(2026)
