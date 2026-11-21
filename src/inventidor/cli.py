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


def _backtest(args) -> None:
    from inventidor.especialistas.quant import backtest, resumir, texto_resumos
    from inventidor.especialistas.tecnico import ler_precos

    series = ler_precos(args.precos)
    tickers = [t.upper() for t in args.ticker] or sorted(series)
    resumos = []
    for t in tickers:
        if len(series.get(t, [])) < 61:
            print(f"{t}: histórico insuficiente (precisa de mais de 60 pregões).")
            continue
        resumos.append(resumir(t, series[t], backtest(t, series[t])))
    print(texto_resumos(resumos))


def _dados(args) -> None:
    from decimal import Decimal as D

    if args.alvo == "selic":
        from inventidor.dados import bcb

        selic = bcb.ultimos("selic_meta", 1)[-1]
        ipca = bcb.ultimos("ipca_mensal", 12)
        ipca12 = bcb.ipca_12_meses(ipca)
        print(f"Selic meta: {selic[1]}% a.a. (em {selic[0]:%d/%m/%Y})")
        print(f"IPCA 12 meses: {ipca12:.2f}%")
        print(f"Juro real: {bcb.juro_real(selic[1], ipca12):.2f}% a.a. (fonte: Banco Central)")
    else:
        from inventidor.dados.cotacoes import baixar_cotacoes, salvar_csv

        series = {t.upper(): baixar_cotacoes(t, args.periodo) for t in args.tickers}
        salvar_csv(series, args.saida)
        for t, c in series.items():
            print(f"{t}: {len(c)} pregões, último {c[-1].data:%d/%m/%Y} a R$ {c[-1].fechamento}")
        print(f"Gravado em {args.saida} (fonte: Yahoo Finance, não oficial)")


def _eventos(args) -> None:
    from datetime import date, timedelta

    from inventidor.dados.cvm import baixar_ipe
    from inventidor.especialistas.noticias import alertas, ler_mapa, texto_alertas

    desde = date.today() - timedelta(days=args.dias)
    docs = baixar_ipe(date.today().year)
    print(texto_alertas(alertas(docs, ler_mapa(args.mapa), desde)))


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
    bt = sub.add_parser("backtest", help="testa a estratégia do Analista Técnico no histórico")
    bt.add_argument("--precos", default="exemplos/precos.csv")
    bt.add_argument("ticker", nargs="*", help="sem tickers, testa todos do arquivo")
    da = sub.add_parser("dados", help="baixa dados reais (precisa de internet)")
    dsub = da.add_subparsers(dest="alvo", required=True)
    dsub.add_parser("selic", help="Selic, IPCA 12 meses e juro real (Banco Central)")
    dc = dsub.add_parser("cotacoes", help="cotações diárias para o Analista Técnico")
    dc.add_argument("tickers", nargs="+")
    dc.add_argument("--periodo", default="1y")
    dc.add_argument("--saida", default="dados/precos.csv")
    ev = sub.add_parser("eventos", help="fatos relevantes e comunicados da CVM (precisa de internet)")
    ev.add_argument("--mapa", default="exemplos/mapa_empresas.csv", help="CSV ticker;nome")
    ev.add_argument("--dias", type=int, default=30)
    args = p.parse_args(argv)

    from inventidor.dados.http import RedeIndisponivel

    try:
        return _executar(args)
    except RedeIndisponivel as e:
        print(f"Sem acesso à fonte de dados: {e}")
        print("Nada foi estimado no lugar. Tente de novo com internet ou use os CSVs manuais.")
        return 1


def _executar(args) -> int:
    if args.comando == "plano":
        _plano(args)
    elif args.comando == "backtest":
        _backtest(args)
    elif args.comando == "dados":
        _dados(args)
    elif args.comando == "eventos":
        _eventos(args)
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
