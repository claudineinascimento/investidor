import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal as D

import pytest

from inventidor import diario
from inventidor.diario import Estado, Item
from inventidor.painel import Painel, criar_servidor


@pytest.fixture
def servidor(tmp_path):
    cam, ops = tmp_path / "d.jsonl", tmp_path / "ops.csv"
    diario.registrar_sugestao(Item(
        id="20261121-<b>X", data=date(2026, 11, 21), ticker="BETA4", tipo="ACAO", quantidade=12,
        preco_limite=D("31.50"), stop=D("29.98"), alvo=D("34.54"), tese="<script>alert(1)</script>",
        parecer_risco="ok"), cam)
    p = Painel(cam, ops)
    srv = criar_servidor(p, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield p, srv.server_address[1], cam, ops
    srv.shutdown()


def post(porta, rota, campos, host=None):
    req = urllib.request.Request(f"http://127.0.0.1:{porta}/{rota}",
                                 data=urllib.parse.urlencode(campos).encode(), method="POST")
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_pagina_escapa_html_e_mostra_fila(servidor):
    p, porta, *_ = servidor
    corpo = urllib.request.urlopen(f"http://127.0.0.1:{porta}/").read().decode()
    assert "<script>alert" not in corpo and "&lt;script&gt;" in corpo
    assert "Comprar 12 BETA4" in corpo


def test_post_sem_token_e_barrado(servidor):
    p, porta, cam, _ = servidor
    status, _ = post(porta, "aprovar", {"id": "20261121-<b>X", "token": "errado"})
    assert status == 403
    assert diario.carregar(cam)["20261121-<b>X"].estado == Estado.SUGERIDA


def test_host_estranho_e_barrado(servidor):
    p, porta, *_ = servidor
    status, _ = post(porta, "aprovar", {"id": "x", "token": p.token}, host="evil.example:80")
    assert status == 403


def test_fluxo_pelo_painel(servidor):
    p, porta, cam, ops = servidor
    id_ = "20261121-<b>X"
    status, corpo = post(porta, "executada", {"id": id_, "token": p.token, "preco": "31,40"})
    assert "SUGERIDA" in corpo or "aprovou" in corpo or "só registro" in corpo  # não pula etapa
    assert diario.carregar(cam)[id_].estado == Estado.SUGERIDA
    post(porta, "aprovar", {"id": id_, "token": p.token})
    status, corpo = post(porta, "executada", {"id": id_, "token": p.token, "preco": "31,40", "custos": "1,2"})
    assert diario.carregar(cam)[id_].estado == Estado.EXECUTADA
    assert "BETA4" in ops.read_text() and "31.40" in ops.read_text()
