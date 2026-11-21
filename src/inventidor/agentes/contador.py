"""Agente Contador ligado ao Claude (Tool Runner do SDK Anthropic).

O agente conversa com o investidor e chama as ferramentas abaixo, que rodam o
código determinístico de apuração. Uso:

    pip install "inventidor[agentes]"   # instala o SDK anthropic
    export ANTHROPIC_API_KEY=...
    inventidor-contador exemplos/operacoes.csv "Quanto devo de IR em outubro?"
"""

from __future__ import annotations

import sys
from pathlib import Path

from inventidor.agentes.definicoes import EQUIPE
from inventidor.carteira import Carteira
from inventidor.impostos.apuracao import apurar_periodo
from inventidor.importador import ler_csv
from inventidor.relatorio import texto_apuracao, texto_carteira


def criar_ferramentas(caminho_csv: str | Path):
    """Ferramentas do Contador, presas a um arquivo de operações."""
    from anthropic import beta_tool  # import tardio: o resto do pacote não depende do SDK

    carteira = Carteira().processar(ler_csv(caminho_csv))
    apuracoes = apurar_periodo(carteira)

    @beta_tool
    def ver_carteira() -> str:
        """Mostra as posições abertas com quantidade, preço médio e custo total."""
        return texto_carteira(carteira)

    @beta_tool
    def listar_apuracoes() -> str:
        """Lista os meses com vendas e o DARF de cada um."""
        if not apuracoes:
            return "Nenhuma venda registrada: não há imposto a apurar."
        return "\n".join(
            f"{a.competencia}: DARF R$ {a.imposto_a_pagar}"
            + (f", vence {a.vencimento:%d/%m/%Y}" if a.vencimento else "")
            for a in apuracoes
        )

    @beta_tool
    def apurar_mes(ano: int, mes: int) -> str:
        """Apuração detalhada do IR de um mês.

        Args:
            ano: ano com quatro dígitos, por exemplo 2026.
            mes: mês de 1 a 12.
        """
        for a in apuracoes:
            if (a.ano, a.mes) == (ano, mes):
                return texto_apuracao(a)
        return f"Sem vendas em {mes:02d}/{ano}: nada a apurar."

    return [ver_carteira, listar_apuracoes, apurar_mes]


def perguntar(caminho_csv: str | Path, pergunta: str) -> str:
    import anthropic

    agente = EQUIPE["contador"]
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=agente.modelo,
        max_tokens=16000,
        system=agente.prompt_sistema,
        output_config={"effort": agente.esforco},
        tools=criar_ferramentas(caminho_csv),
        messages=[{"role": "user", "content": pergunta}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        return "O modelo recusou a pergunta. Reformule ou consulte o relatório da linha de comando."
    return "".join(b.text for b in final.content if b.type == "text")


def main() -> int:
    if len(sys.argv) < 3:
        print('Uso: inventidor-contador operacoes.csv "sua pergunta"')
        return 2
    print(perguntar(sys.argv[1], " ".join(sys.argv[2:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
