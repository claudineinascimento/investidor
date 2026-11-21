"""Linha de comando.

    inventidor carteira operacoes.csv
    inventidor apurar operacoes.csv [--mes 2026-10]
    inventidor plano --valor 10000 --aporte 500 --gastos 3000 --reserva 18000 \\
        --prazo 10 --perfil moderado --fundamentos f.csv --precos p.csv
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from inventidor.carteira import Carteira
from inventidor.impostos.apuracao import apurar_periodo
from inventidor.importador import ler_csv
from inventidor.relatorio import AVISO_LEGAL, texto_apuracao, texto_carteira


def _plano(args) -> None:
    from inventidor.especialistas.consultor import Perfil, PerfilRisco, definir_politica, plano_aportes
    from inventidor.especialistas.fundamentalista import ler_fundamentos
    from inventidor.especialistas.orquestrador import (
        plano_do_mes, texto_dicas, texto_plano, texto_plano_aportes,
    )
    from inventidor.especialistas.tecnico import ler_precos

    perfil = Perfil(
        valor_disponivel=Decimal(args.valor), aporte_mensal=Decimal(args.aporte),
        gastos_mensais=Decimal(args.gastos), reserva_atual=Decimal(args.reserva),
        prazo_anos=args.prazo, perfil_risco=PerfilRisco(args.perfil),
    )
    politica = definir_politica(perfil)
    print(f"Política do Consultor (perfil {args.perfil}, prazo {args.prazo} anos)")
    for c, pct in politica.alocacao.items():
        print(f"  {c.value}: {pct * 100:.0f}%")
    print(f"  Limite por ação: {politica.limite_por_acao * 100:.0f}% da parte de ações; "
          f"por setor: {politica.limite_por_setor * 100:.0f}%; "
          f"alerta de queda mensal: {politica.alerta_perda_mensal * 100:.0f}%")
    print()
    print(texto_plano_aportes(plano_aportes(politica, args.meses)))
    print()
    plano = plano_do_mes(
        politica, perfil.valor_disponivel,
        ler_fundamentos(args.fundamentos), ler_precos(args.precos),
    )
    print(texto_plano(plano, "Plano do mês 0 (valor inicial)"))
    print()
    print(texto_dicas())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inventidor")
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("carteira", help="posições e preço médio")
    c.add_argument("csv")
    a = sub.add_parser("apurar", help="apuração mensal do IR e DARF")
    a.add_argument("csv")
    a.add_argument("--mes", help="AAAA-MM; sem isso, mostra todos os meses")
    pl = sub.add_parser("plano", help="política, plano de aportes e sugestões do mês")
    pl.add_argument("--valor", default="10000", help="valor para investir agora")
    pl.add_argument("--aporte", default="500", help="aporte mensal")
    pl.add_argument("--gastos", default="3000", help="gastos mensais (para a reserva)")
    pl.add_argument("--reserva", default="18000", help="reserva de emergência que já existe")
    pl.add_argument("--prazo", type=int, default=10, help="prazo em anos")
    pl.add_argument("--perfil", default="moderado", choices=["conservador", "moderado", "arrojado"])
    pl.add_argument("--meses", type=int, default=12)
    pl.add_argument("--fundamentos", default="exemplos/fundamentos.csv")
    pl.add_argument("--precos", default="exemplos/precos.csv")
    args = p.parse_args(argv)

    if args.comando == "plano":
        _plano(args)
    else:
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
