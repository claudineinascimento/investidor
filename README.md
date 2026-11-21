# Inventidor

Equipe de agentes de IA para acompanhar uma carteira de ações na B3: busca, análise,
acompanhamento e sugestões de compra e venda. **Os agentes sugerem; quem decide e
confirma cada ordem é você.**

Proposta completa (agentes, fluxo, fontes de dados, guardrails e roadmap):
[documento do projeto](https://claude.ai/artifact/CTVfAb93YBqQm44M1f5LyM).

## A equipe

| Agente | Faz | Fase |
| --- | --- | --- |
| Contador | IR mensal, DARF, compensação de prejuízo | 1 (pronto) |
| Consultor | Perfil, quanto vai para a bolsa, limites | 2 |
| Analista Fundamentalista | Ranking de empresas e preço justo | 2 |
| Analista Técnico | Entrada, alvo e stop | 2 |
| Gestor de Risco | Aprova, ajusta ou veta sugestões | 2 |
| Orquestrador e Conformidade | Fila diária de decisões | 2 |
| Notícias e Eventos | Fatos relevantes e resultados | 3 |
| Quant / Backtest | Testa estratégias e mede acertos | 3 |
| Mesa | Boleta pronta para você confirmar | 4 |

As definições (papel, instruções, modelo) estão em `src/inventidor/agentes/definicoes.py`.

## Fase 1: Contador

Cálculos feitos em código (a IA só explica, nunca calcula imposto de cabeça):

- preço médio com custos de corretagem e taxas;
- separação automática de day trade (compra e venda no mesmo dia);
- isenção de vendas de ações até R$ 20 mil no mês (não vale para ETFs, FIIs nem day trade);
- alíquotas de 15% (comum), 20% (day trade) e 20% (FIIs);
- compensação de prejuízo por modalidade, mês a mês;
- IRRF ("dedo-duro") deduzido do imposto;
- DARF código 6015, mínimo de R$ 10 (abaixo disso acumula) e vencimento no último dia útil do mês seguinte.

As regras ficam numa tabela (`impostos/regras.py`) para serem atualizadas quando a lei mudar.

### Uso

```bash
pip install -e ".[dev]"
inventidor carteira exemplos/operacoes.csv
inventidor apurar exemplos/operacoes.csv --mes 2026-10
pytest
```

O CSV tem as colunas `data;ticker;tipo;lado;quantidade;preco;custos;irrf`
(veja `exemplos/operacoes.csv`). Tipo: `ACAO`, `FII` ou `ETF`; lado: `C` ou `V`.

### Conversar com o agente Contador

```bash
pip install -e ".[agentes]"
export ANTHROPIC_API_KEY=...
inventidor-contador exemplos/operacoes.csv "Quanto devo de IR em outubro e até quando pago?"
```

## Limitações conhecidas

- Feriados não entram no cálculo do vencimento (só fins de semana).
- Venda a descoberto, opções, subscrições, desdobramentos e bonificações ainda não são tratados.
- Leitura automática do PDF da nota de corretagem e do extrato da B3 vem na próxima etapa.
- Prejuízo em mês isento entra no saldo a compensar (`compensar_prejuizo_mes_isento`); confirme esse
  entendimento com seu contador.

## Aviso

Ferramenta de apoio à decisão para uso pessoal. Não é recomendação de investimento nem
substitui um contador. Confira os valores antes de pagar ou declarar.
