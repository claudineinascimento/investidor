"""Linha de comando.

    inventidor carteira operacoes.csv
    inventidor apurar operacoes.csv [--mes 2026-10]
"""

from __future__ import annotations

import argparse
import sys

from inventidor.carteira import Carteira
from inventidor.impostos.apuracao import apurar_periodo
from inventidor.importador import ler_csv
from inventidor.relatorio import AVISO_LEGAL, texto_apuracao, texto_carteira


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inventidor")
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("carteira", help="posições e preço médio")
    c.add_argument("csv")
    a = sub.add_parser("apurar", help="apuração mensal do IR e DARF")
    a.add_argument("csv")
    a.add_argument("--mes", help="AAAA-MM; sem isso, mostra todos os meses")
    args = p.parse_args(argv)

    carteira = Carteira().processar(ler_csv(args.csv))
    if args.comando == "carteira":
        print(texto_carteira(carteira))
    else:
        apuracoes = apurar_periodo(carteira)
        if args.mes:
            ano, mes = (int(x) for x in args.mes.split("-"))
            apuracoes = [x for x in apuracoes if (x.ano, x.mes) == (ano, mes)]
            if not apuracoes:
                print(f"Sem vendas em {args.mes}: nada a apurar.")
        for ap in apuracoes:
            print(texto_apuracao(ap))
            print()
    print(AVISO_LEGAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
