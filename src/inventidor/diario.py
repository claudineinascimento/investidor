"""Diário de decisões: quem sugeriu, o que você decidiu e o que foi executado.

Cada sugestão passa por estados, e só você move de um para o outro:

    SUGERIDA -> APROVADA -> EXECUTADA
        \\-> RECUSADA        (recusada também vale depois de aprovada, até executar)

O diário é um arquivo JSONL só de acréscimo (nada é apagado), útil para auditoria,
para o Quant medir o acerto dos agentes e para o Contador. Quando você informa que
executou a ordem na corretora, a operação entra no CSV de operações e passa a valer
na apuração de imposto. O Inventidor nunca envia ordens.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

DIARIO_PADRAO = Path("dados/diario.jsonl")
COLUNAS_OPERACOES = ["data", "ticker", "tipo", "lado", "quantidade", "preco", "custos", "irrf"]


class Estado(str, Enum):
    SUGERIDA = "SUGERIDA"
    APROVADA = "APROVADA"
    RECUSADA = "RECUSADA"
    EXECUTADA = "EXECUTADA"


class ErroDiario(ValueError):
    pass


@dataclass
class Item:
    id: str
    data: date
    ticker: str
    tipo: str  # ACAO, FII ou ETF
    quantidade: int
    preco_limite: Decimal
    stop: Decimal
    alvo: Decimal
    tese: str
    parecer_risco: str
    estado: Estado = Estado.SUGERIDA
    execucao: dict | None = None
    motivo_recusa: str = ""

    @property
    def valor(self) -> Decimal:
        return self.quantidade * self.preco_limite


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gravar(caminho: Path, evento: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps({"em": _agora(), **evento}, ensure_ascii=False) + "\n")


def carregar(caminho: Path = DIARIO_PADRAO) -> dict[str, Item]:
    itens: dict[str, Item] = {}
    if not caminho.exists():
        return itens
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        e = json.loads(linha)
        if e["evento"] == "sugerida":
            itens[e["id"]] = Item(
                id=e["id"], data=date.fromisoformat(e["data"]), ticker=e["ticker"], tipo=e["tipo"],
                quantidade=e["quantidade"], preco_limite=Decimal(e["preco_limite"]),
                stop=Decimal(e["stop"]), alvo=Decimal(e["alvo"]), tese=e["tese"],
                parecer_risco=e["parecer_risco"],
            )
        else:
            item = itens[e["id"]]
            if e["evento"] == "aprovada":
                item.estado = Estado.APROVADA
            elif e["evento"] == "recusada":
                item.estado, item.motivo_recusa = Estado.RECUSADA, e.get("motivo", "")
            elif e["evento"] == "executada":
                item.estado, item.execucao = Estado.EXECUTADA, e
    return itens


def registrar_sugestao(item: Item, caminho: Path = DIARIO_PADRAO) -> bool:
    """Grava a sugestão se o id ainda não existe. Devolve False se já estava lá."""
    if item.id in carregar(caminho):
        return False
    _gravar(caminho, {
        "evento": "sugerida", "id": item.id, "data": item.data.isoformat(), "ticker": item.ticker,
        "tipo": item.tipo, "quantidade": item.quantidade, "preco_limite": str(item.preco_limite),
        "stop": str(item.stop), "alvo": str(item.alvo), "tese": item.tese,
        "parecer_risco": item.parecer_risco,
    })
    return True


def _item(itens: dict[str, Item], id: str) -> Item:
    if id not in itens:
        raise ErroDiario(f"Sugestão {id!r} não existe. Veja `inventidor fila`.")
    return itens[id]


def aprovar(id: str, caminho: Path = DIARIO_PADRAO) -> Item:
    itens = carregar(caminho)
    item = _item(itens, id)
    if item.estado != Estado.SUGERIDA:
        raise ErroDiario(f"{id} está {item.estado.value}: só dá para aprovar o que está SUGERIDA.")
    _gravar(caminho, {"evento": "aprovada", "id": id})
    item.estado = Estado.APROVADA
    return item


def recusar(id: str, motivo: str = "", caminho: Path = DIARIO_PADRAO) -> Item:
    itens = carregar(caminho)
    item = _item(itens, id)
    if item.estado in (Estado.RECUSADA, Estado.EXECUTADA):
        raise ErroDiario(f"{id} já está {item.estado.value}.")
    _gravar(caminho, {"evento": "recusada", "id": id, "motivo": motivo})
    item.estado, item.motivo_recusa = Estado.RECUSADA, motivo
    return item


def executar(
    id: str, preco: Decimal, quantidade: int | None = None, custos: Decimal = Decimal("0"),
    dia: date | None = None, operacoes_csv: Path | None = None, caminho: Path = DIARIO_PADRAO,
) -> Item:
    """Registra que VOCÊ executou a ordem na corretora e a leva ao CSV de operações."""
    itens = carregar(caminho)
    item = _item(itens, id)
    if item.estado != Estado.APROVADA:
        raise ErroDiario(f"{id} está {item.estado.value}: só registro execução do que você APROVOU.")
    qtd = quantidade or item.quantidade
    dia = dia or date.today()
    if preco > item.preco_limite * Decimal("1.02"):
        raise ErroDiario(
            f"Preço R$ {preco} está mais de 2% acima do limite sugerido (R$ {item.preco_limite}). "
            "Confira o valor; se for isso mesmo, recuse a sugestão e registre a operação à mão."
        )
    _gravar(caminho, {
        "evento": "executada", "id": id, "data": dia.isoformat(), "quantidade": qtd,
        "preco": str(preco), "custos": str(custos),
    })
    if operacoes_csv:
        novo = not operacoes_csv.exists()
        operacoes_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(operacoes_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            if novo:
                w.writerow(COLUNAS_OPERACOES)
            w.writerow([dia.isoformat(), item.ticker, item.tipo, "C", qtd, preco, custos, ""])
    item.estado = Estado.EXECUTADA
    return item


def texto_fila(itens: dict[str, Item], estados: tuple[Estado, ...] = (Estado.SUGERIDA, Estado.APROVADA)) -> str:
    fila = [i for i in itens.values() if i.estado in estados]
    if not fila:
        return "Nada pendente."
    l = ["Fila de decisões (nada é enviado sem você)"]
    for i in sorted(fila, key=lambda x: (x.estado.value, x.data)):
        l.append(
            f"  [{i.estado.value}] {i.id}: comprar {i.quantidade} {i.ticker} a até R$ {i.preco_limite} "
            f"(R$ {i.valor:.2f}) | stop {i.stop}, alvo {i.alvo}"
        )
        l.append(f"      Risco: {i.parecer_risco}")
    return "\n".join(l)
