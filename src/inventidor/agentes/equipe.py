"""Conversa com a equipe da Fase 2 pelo Orquestrador (Tool Runner do SDK Anthropic).

O Orquestrador chama as ferramentas de cada especialista (Consultor,
Fundamentalista, Técnico, Risco) e explica o plano. Ele não envia ordens.

    pip install -e ".[agentes]"
    export ANTHROPIC_API_KEY=...
    inventidor-equipe "Tenho 10 mil e posso aportar 500 por mês. O que faço este mês?"
"""

from __future__ import annotations

import sys
from decimal import Decimal

from inventidor.agentes.definicoes import EQUIPE
from inventidor.especialistas.consultor import Perfil, PerfilRisco, definir_politica, plano_aportes
from inventidor.especialistas.fundamentalista import ler_fundamentos, ranking
from inventidor.especialistas.orquestrador import (
    plano_do_mes, texto_dicas, texto_plano, texto_plano_aportes,
)
from inventidor.especialistas.tecnico import analisar, ler_precos


def criar_ferramentas(fundamentos_csv: str, precos_csv: str):
    from anthropic import beta_tool

    empresas = ler_fundamentos(fundamentos_csv)
    precos = ler_precos(precos_csv)

    def _perfil(valor, aporte, gastos, reserva, prazo, perfil) -> Perfil:
        return Perfil(Decimal(str(valor)), Decimal(str(aporte)), Decimal(str(gastos)),
                      Decimal(str(reserva)), int(prazo), PerfilRisco(perfil))

    @beta_tool
    def consultor_plano(valor: float, aporte_mensal: float, gastos_mensais: float,
                        reserva_atual: float, prazo_anos: int, perfil: str, meses: int = 12) -> str:
        """Consultor: política de investimento e plano de aportes mensais.

        Args:
            valor: valor para investir agora, em reais.
            aporte_mensal: quanto pode aportar por mês, em reais.
            gastos_mensais: gastos mensais da família, para dimensionar a reserva.
            reserva_atual: reserva de emergência que já existe, em reais.
            prazo_anos: por quanto tempo o dinheiro pode ficar investido.
            perfil: conservador, moderado ou arrojado.
            meses: meses de projeção do plano de aportes.
        """
        pol = definir_politica(_perfil(valor, aporte_mensal, gastos_mensais, reserva_atual, prazo_anos, perfil))
        aloc = "\n".join(f"{c.value}: {p * 100:.0f}%" for c, p in pol.alocacao.items())
        obs = "\n".join(f"- {o}" for o in pol.observacoes)
        return f"{aloc}\n{obs}\n\n{texto_plano_aportes(plano_aportes(pol, meses))}"

    @beta_tool
    def plano_do_mes_equipe(valor_mes: float, aporte_mensal: float, gastos_mensais: float,
                            reserva_atual: float, prazo_anos: int, perfil: str) -> str:
        """Orquestrador: sugestões do mês já passadas por Fundamentalista, Técnico e Risco.

        Args:
            valor_mes: valor a aplicar neste mês, em reais.
            aporte_mensal: aporte mensal previsto, em reais.
            gastos_mensais: gastos mensais da família.
            reserva_atual: reserva de emergência que já existe.
            prazo_anos: prazo do investimento em anos.
            perfil: conservador, moderado ou arrojado.
        """
        pol = definir_politica(_perfil(valor_mes, aporte_mensal, gastos_mensais, reserva_atual, prazo_anos, perfil))
        return texto_plano(plano_do_mes(pol, Decimal(str(valor_mes)), empresas, precos))

    @beta_tool
    def analisar_empresa(ticker: str) -> str:
        """Fundamentalista e Técnico: análise completa de uma empresa da base.

        Args:
            ticker: código da ação, por exemplo BETA4.
        """
        t = ticker.strip().upper()
        av = next((a for a in ranking(empresas) if a.fundamentos.ticker == t), None)
        if not av:
            return f"{t} não está na base de fundamentos."
        partes = [
            f"{t} ({av.fundamentos.setor}): nota {av.nota}/10, aprovada: {'sim' if av.aprovada else 'não'}",
            "Pontos: " + "; ".join(av.pontos),
            "Alertas: " + ("; ".join(av.alertas) or "nenhum"),
            f"Preço justo: {av.preco_justo:.2f}" if av.preco_justo else "Sem preço justo",
        ]
        if t in precos:
            l = analisar(t, precos[t])
            partes.append(f"Técnico ({l.data}): {l.sinal.value}. {l.motivo} Entrada {l.entrada_min}-{l.entrada_max}, stop {l.stop}, alvo {l.alvo}")
        return "\n".join(partes)

    @beta_tool
    def dicas_da_equipe() -> str:
        """Dicas práticas de cada especialista."""
        return texto_dicas()

    return [consultor_plano, plano_do_mes_equipe, analisar_empresa, dicas_da_equipe]


def perguntar(pergunta: str, fundamentos_csv: str = "exemplos/fundamentos.csv",
              precos_csv: str = "exemplos/precos.csv") -> str:
    import anthropic

    agente = EQUIPE["orquestrador"]
    runner = anthropic.Anthropic().beta.messages.tool_runner(
        model=agente.modelo,
        max_tokens=16000,
        system=agente.prompt_sistema,
        output_config={"effort": agente.esforco},
        tools=criar_ferramentas(fundamentos_csv, precos_csv),
        messages=[{"role": "user", "content": pergunta}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        return "O modelo recusou a pergunta. Use `inventidor plano` na linha de comando."
    return "".join(b.text for b in final.content if b.type == "text")


def main() -> int:
    if len(sys.argv) < 2:
        print('Uso: inventidor-equipe "sua pergunta"')
        return 2
    print(perguntar(" ".join(sys.argv[1:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
