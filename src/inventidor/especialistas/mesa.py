"""Mesa (Assessor): transforma uma sugestão aprovada em boleta para VOCÊ digitar.

O Inventidor não tem acesso à sua corretora: a boleta é um roteiro para conferir
e digitar no home broker ou no aplicativo. Se um dia houver integração com a
API de uma corretora, ela entra aqui, sempre com confirmação sua a cada ordem.
"""

from __future__ import annotations

from datetime import date

from inventidor.diario import ErroDiario, Estado, Item


def ticker_na_boleta(item: Item) -> str:
    """No mercado fracionário (menos de 100) o código leva um F no final."""
    return f"{item.ticker}F" if item.quantidade < 100 else item.ticker


def boleta(item: Item, validade: date | None = None) -> str:
    if item.estado != Estado.APROVADA:
        raise ErroDiario(f"{item.id} está {item.estado.value}: a boleta só sai depois de você aprovar.")
    val = f"{validade:%d/%m/%Y}" if validade else "válida só para o dia"
    return "\n".join([
        f"BOLETA {item.id}  (confira cada campo antes de enviar)",
        f"  Ativo:        {ticker_na_boleta(item)}",
        f"  Lado:         COMPRA",
        f"  Quantidade:   {item.quantidade}",
        f"  Tipo:         ORDEM LIMITADA (nunca a mercado)",
        f"  Preço limite: R$ {item.preco_limite}",
        f"  Validade:     {val}",
        f"  Valor máximo: R$ {item.valor:.2f} mais custos da sua corretora",
        "",
        "Depois de enviar:",
        f"  - Stop mental ou ordem stop em R$ {item.stop}; alvo em R$ {item.alvo}.",
        "  - Se não executar hoje, não persiga o preço: espere o próximo plano.",
        f"  - Executou? Registre: inventidor executada {item.id} --preco <preço> --custos <custos>",
    ])
