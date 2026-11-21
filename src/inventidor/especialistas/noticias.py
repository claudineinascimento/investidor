"""Notícias e Eventos: prioriza documentos da CVM das empresas que você acompanha.

Não interpreta o conteúdo do documento: só ordena por relevância (categoria e
palavras-chave) e liga cada documento ao ticker. O agente de IA lê o link e
explica o impacto; o investidor decide.
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from pathlib import Path

from inventidor.dados.cvm import Documento


class Prioridade(IntEnum):
    BAIXA = 1
    MEDIA = 2
    ALTA = 3


CATEGORIA_BASE = {
    "fato relevante": Prioridade.ALTA,
    "comunicado ao mercado": Prioridade.MEDIA,
    "aviso aos acionistas": Prioridade.MEDIA,
}

# Palavras no assunto que sobem a prioridade e dizem o que olhar.
PALAVRAS = {
    "dividendo": "provento",
    "juros sobre capital": "provento",
    "jcp": "provento",
    "bonificacao": "evento corporativo (bonificação)",
    "desdobramento": "evento corporativo (desdobramento)",
    "grupamento": "evento corporativo (grupamento)",
    "recuperacao judicial": "risco de crédito",
    "falencia": "risco de crédito",
    "aquisicao": "fusão ou aquisição",
    "fusao": "fusão ou aquisição",
    "incorporacao": "fusão ou aquisição",
    "oferta publica": "oferta de ações ou OPA",
    "follow-on": "oferta de ações ou OPA",
    "resultado": "resultado",
    "guidance": "projeção da empresa",
    "investigacao": "risco regulatório",
    "rebaixamento": "risco de crédito",
    "recompra": "recompra de ações",
}


def _norm(t: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn"
    )


@dataclass(frozen=True)
class Alerta:
    ticker: str
    data: date
    prioridade: Prioridade
    motivo: str
    documento: Documento


def ler_mapa(caminho: str | Path) -> dict[str, str]:
    """CSV 'ticker;nome': trecho do nome da companhia como aparece na CVM."""
    linhas = Path(caminho).read_text(encoding="utf-8-sig").splitlines()
    return {
        l["ticker"].strip().upper(): _norm(l["nome"].strip())
        for l in csv.DictReader(linhas, delimiter=";")
    }


def alertas(
    docs: list[Documento], mapa: dict[str, str], desde: date | None = None
) -> list[Alerta]:
    saida = []
    for d in docs:
        if desde and d.data < desde:
            continue
        nome = _norm(d.empresa)
        ticker = next((t for t, trecho in mapa.items() if trecho in nome), None)
        if not ticker:
            continue
        base = CATEGORIA_BASE.get(_norm(d.categoria))
        if base is None:
            continue
        texto = _norm(f"{d.assunto} {d.tipo}")
        achados = sorted({m for p, m in PALAVRAS.items() if p in texto})
        prio = Prioridade.ALTA if (base == Prioridade.ALTA or achados) else base
        motivo = d.categoria + (f" ({', '.join(achados)})" if achados else "")
        saida.append(Alerta(ticker, d.data, prio, motivo, d))
    return sorted(saida, key=lambda a: (a.prioridade, a.data), reverse=True)


def texto_alertas(lista: list[Alerta], limite: int = 15) -> str:
    if not lista:
        return "Nenhum fato relevante ou comunicado novo das empresas acompanhadas."
    l = ["Alertas de Notícias e Eventos (fonte: CVM)"]
    for a in lista[:limite]:
        l.append(f"  [{a.prioridade.name}] {a.ticker} {a.data:%d/%m/%Y}: {a.motivo}")
        if a.documento.assunto:
            l.append(f"      Assunto: {a.documento.assunto}")
        if a.documento.link:
            l.append(f"      Documento: {a.documento.link}")
    return "\n".join(l)
