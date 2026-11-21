"""Orquestrador: junta os especialistas e monta o plano do mês.

Fluxo: Consultor divide o valor do mês entre as classes -> Fundamentalista
ranqueia empresas -> Técnico diz se é hora de entrar -> Gestor de Risco
aprova, ajusta ou veta -> sai uma lista de sugestões para VOCÊ decidir.
Nenhuma ordem é enviada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal

from inventidor.diario import Item
from inventidor.especialistas.consultor import Classe, MesPlano, Politica, distribuir_valor
from inventidor.especialistas.dicas import DICAS
from inventidor.especialistas.fundamentalista import Avaliacao, Fundamentos, ranking
from inventidor.especialistas.risco import Parecer, Veredito, avaliar_compra
from inventidor.especialistas.tecnico import Candle, Leitura, Sinal, analisar

ZERO = Decimal("0")
NOTA_MINIMA = 5
VALOR_POR_POSICAO = Decimal("400")  # referência para decidir quantas ações comprar no mês
MAX_POSICOES_MES = 5


@dataclass
class Sugestao:
    ticker: str
    setor: str
    quantidade: int
    preco_limite: Decimal
    stop: Decimal
    alvo: Decimal
    valor: Decimal
    nota: int
    preco_justo: Decimal | None
    margem_seguranca: Decimal | None
    parecer: Parecer
    tese: list[str]
    leitura: Leitura

    @property
    def ticker_fracionario(self) -> str:
        return f"{self.ticker}F" if self.quantidade < 100 else self.ticker


@dataclass
class PlanoMes:
    valor_mes: Decimal
    distribuicao: dict[Classe, Decimal]
    sugestoes: list[Sugestao] = field(default_factory=list)
    vetadas: list[tuple[str, Parecer]] = field(default_factory=list)
    aguardar: list[Leitura] = field(default_factory=list)
    sobra_acoes: Decimal = ZERO
    observacoes: list[str] = field(default_factory=list)


def plano_do_mes(
    politica: Politica,
    valor_mes: Decimal,
    empresas: list[Fundamentos],
    precos: dict[str, list[Candle]],
    atual_por_classe: dict[Classe, Decimal] | None = None,
    posicoes_acoes: dict[str, tuple[str, Decimal]] | None = None,
) -> PlanoMes:
    atual = dict(atual_por_classe or {})
    posicoes = dict(posicoes_acoes or {})
    dist = distribuir_valor(politica, valor_mes, atual)
    plano = PlanoMes(valor_mes=valor_mes, distribuicao=dist, observacoes=list(politica.observacoes))

    investido_depois = sum(
        (atual.get(c, ZERO) + dist[c] for c in politica.alocacao), ZERO
    )
    parcela_acoes_alvo = investido_depois * politica.alocacao[Classe.ACOES]
    verba = dist[Classe.ACOES]
    if verba <= 0:
        return plano

    candidatas: list[tuple[Avaliacao, Leitura]] = []
    for av in ranking(empresas):
        if not av.aprovada or av.nota < NOTA_MINIMA:
            continue
        if av.margem_seguranca is not None and av.margem_seguranca <= 0:
            continue
        serie = precos.get(av.fundamentos.ticker)
        if not serie:
            continue
        leitura = analisar(av.fundamentos.ticker, serie)
        if leitura.sinal == Sinal.COMPRAR:
            candidatas.append((av, leitura))
        elif leitura.sinal == Sinal.AGUARDAR:
            plano.aguardar.append(leitura)

    if verba < VALOR_POR_POSICAO:
        plano.observacoes.append(
            f"Verba de ações do mês (R$ {verba:.2f}) é pequena: compre uma ação por vez, a mais "
            "abaixo do alvo, ou junte 2 a 3 meses de aporte antes de comprar."
        )
    if not candidatas:
        plano.sobra_acoes = verba
        plano.observacoes.append(
            "Nenhuma ação passou por todos os filtros este mês: a verba de ações fica na renda "
            "fixa até a próxima análise."
        )
        return plano

    n = int(min(len(candidatas), MAX_POSICOES_MES, max(1, verba // VALOR_POR_POSICAO)))
    # Já nasce dentro do limite por ação, para o Risco só intervir quando precisar.
    por_posicao = min(verba / n, politica.limite_por_acao * parcela_acoes_alvo)
    usado = ZERO
    for av, leitura in candidatas[:n]:
        f = av.fundamentos
        parecer = avaliar_compra(
            ticker=f.ticker, setor=f.setor, valor=por_posicao, risco_pct=leitura.risco_pct,
            politica=politica, parcela_acoes_alvo=parcela_acoes_alvo,
            patrimonio_investido=investido_depois, posicoes=posicoes,
        )
        if parecer.veredito == Veredito.VETADO:
            plano.vetadas.append((f.ticker, parecer))
            continue
        qtd = int((parecer.valor / leitura.entrada_max).to_integral_value(rounding=ROUND_DOWN))
        if qtd == 0:
            plano.vetadas.append((f.ticker, Parecer(Veredito.VETADO, ZERO, ("Valor não compra 1 ação.",))))
            continue
        valor = (qtd * leitura.entrada_max).quantize(Decimal("0.01"))
        usado += valor
        _, ja = posicoes.get(f.ticker, (f.setor, ZERO))
        posicoes[f.ticker] = (f.setor, ja + valor)
        plano.sugestoes.append(
            Sugestao(
                ticker=f.ticker, setor=f.setor, quantidade=qtd, preco_limite=leitura.entrada_max,
                stop=leitura.stop, alvo=leitura.alvo, valor=valor, nota=av.nota,
                preco_justo=av.preco_justo, margem_seguranca=av.margem_seguranca,
                parecer=parecer, tese=av.pontos, leitura=leitura,
            )
        )
    plano.sobra_acoes = verba - usado
    if plano.sobra_acoes > 0:
        plano.observacoes.append(
            f"R$ {plano.sobra_acoes:.2f} da verba de ações não foram usados (limites de risco ou "
            "arredondamento de lote): deixe na renda fixa para o próximo mês."
        )
    return plano


SUGESTAO_CLASSE = {
    Classe.RESERVA: "Tesouro Selic ou CDB com liquidez diária de banco grande (FGC).",
    Classe.RENDA_FIXA: "Tesouro Selic para curto prazo; Tesouro IPCA+ ou CDB/LCI/LCA para prazos longos.",
    Classe.FIIS: "Um fundo de papel (recebíveis) e um de tijolo (logística ou lajes), ou um FII de FIIs para começar.",
    Classe.ETF: "Um ETF que replica o Ibovespa e, se quiser exposição ao exterior, um ETF de S&P 500.",
}


def texto_plano(plano: PlanoMes, titulo: str = "Plano do mês") -> str:
    l = [titulo, f"Valor do mês: R$ {plano.valor_mes:.2f}", "", "Divisão do Consultor:"]
    for c, v in plano.distribuicao.items():
        if v > 0:
            dica = SUGESTAO_CLASSE.get(c, "ver sugestões abaixo")
            l.append(f"  {c.value}: R$ {v:.2f}  ({dica})")
    if plano.sugestoes:
        l += ["", "Sugestões de ações (você decide e confirma cada uma):"]
        for s in plano.sugestoes:
            pj = f"preço justo R$ {s.preco_justo:.2f}, desconto {s.margem_seguranca:.0f}%" if s.preco_justo else "sem preço justo"
            l.append(
                f"  {s.ticker_fracionario}: comprar {s.quantidade} a até R$ {s.preco_limite} "
                f"(ordem limitada) = R$ {s.valor:.2f}"
            )
            l.append(f"     stop R$ {s.stop}, alvo R$ {s.alvo} | nota {s.nota}/10, {pj}")
            l.append(f"     Tese: {'; '.join(s.tese[:4])}")
            l.append(f"     Técnico: {s.leitura.motivo}")
            l.append(f"     Risco: {s.parecer.veredito.value} - {' '.join(s.parecer.motivos)}")
    if plano.aguardar:
        l += ["", "Lista de espera (boas empresas, preço esticado):"]
        l += [f"  {x.ticker}: {x.motivo}" for x in plano.aguardar]
    if plano.vetadas:
        l += ["", "Vetadas pelo Gestor de Risco:"]
        l += [f"  {t}: {' '.join(p.motivos)}" for t, p in plano.vetadas]
    if plano.observacoes:
        l += ["", "Observações:"] + [f"  - {o}" for o in plano.observacoes]
    return "\n".join(l)


def texto_plano_aportes(plano: list[MesPlano]) -> str:
    classes = [c for c in Classe if any(m.aporte[c] for m in plano)]
    curto = {Classe.RESERVA: "Reserva", Classe.RENDA_FIXA: "Renda fixa", Classe.ACOES: "Ações",
             Classe.FIIS: "FIIs", Classe.ETF: "ETF"}
    cab = f"{'Mês':>4}  " + "  ".join(f"{curto[c]:>14}" for c in classes) + f"  {'Total acumulado':>16}"
    l = ["Plano de aportes (sem supor rentabilidade)", cab]
    for m in plano:
        total = sum(m.acumulado.values(), ZERO)
        l.append(
            f"{m.mes:>4}  " + "  ".join(f"{m.aporte[c]:>14.2f}" for c in classes) + f"  {total:>16.2f}"
        )
    return "\n".join(l)


def itens_do_diario(plano: PlanoMes, dia: date) -> list[Item]:
    """Converte as sugestões do plano em itens da fila de decisões."""
    return [
        Item(
            id=f"{dia:%Y%m%d}-{s.ticker}", data=dia, ticker=s.ticker, tipo="ACAO",
            quantidade=s.quantidade, preco_limite=s.preco_limite, stop=s.stop, alvo=s.alvo,
            tese="; ".join(s.tese[:4]),
            parecer_risco=f"{s.parecer.veredito.value}: {' '.join(s.parecer.motivos)}",
        )
        for s in plano.sugestoes
    ]


def texto_dicas() -> str:
    l = ["Dicas da equipe"]
    for quem, dicas in DICAS.items():
        l.append(f"  {quem}:")
        l += [f"    - {d}" for d in dicas]
    return "\n".join(l)
