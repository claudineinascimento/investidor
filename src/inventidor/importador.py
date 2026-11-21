"""Importa operações de um CSV (uma linha por operação da nota de corretagem).

Colunas: data;ticker;tipo;lado;quantidade;preco;custos;irrf
- data: AAAA-MM-DD ou DD/MM/AAAA
- tipo: ACAO, FII ou ETF
- lado: C (compra) ou V (venda)
- preco, custos, irrf: aceita vírgula ou ponto decimal; custos e irrf são opcionais
Separador: ponto e vírgula (padrão de planilhas em português) ou vírgula.

Leitura automática do PDF da nota de corretagem e do extrato da B3 fica
para uma próxima etapa; por ora, exporte da corretora ou preencha a planilha.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from inventidor.modelos import Lado, Operacao, TipoAtivo


class ErroImportacao(ValueError):
    pass


def _data(texto: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto.strip(), fmt).date()
        except ValueError:
            continue
    raise ErroImportacao(f"Data inválida: {texto!r}")


def _decimal(texto: str | None) -> Decimal:
    if texto is None or not texto.strip():
        return Decimal("0")
    t = texto.strip().replace("R$", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation as e:
        raise ErroImportacao(f"Número inválido: {texto!r}") from e


def ler_csv(caminho: str | Path) -> list[Operacao]:
    texto = Path(caminho).read_text(encoding="utf-8-sig")
    separador = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    leitor = csv.DictReader(texto.splitlines(), delimiter=separador)
    operacoes: list[Operacao] = []
    for n, linha in enumerate(leitor, start=2):
        linha = {k.strip().lower(): (v or "") for k, v in linha.items() if k}
        try:
            operacoes.append(
                Operacao(
                    data=_data(linha["data"]),
                    ticker=linha["ticker"].strip().upper(),
                    tipo=TipoAtivo(linha["tipo"].strip().upper()),
                    lado=Lado(linha["lado"].strip().upper()[:1]),
                    quantidade=int(linha["quantidade"]),
                    preco=_decimal(linha["preco"]),
                    custos=_decimal(linha.get("custos")),
                    irrf=_decimal(linha.get("irrf")),
                )
            )
        except (KeyError, ValueError) as e:
            raise ErroImportacao(f"Linha {n}: {e}") from e
    return operacoes
