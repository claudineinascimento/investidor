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
| Consultor | Perfil, quanto vai para a bolsa, limites, plano de aportes | 2 (pronto) |
| Analista Fundamentalista | Filtros, nota de 0 a 10 e preço justo (Graham e Bazin) | 2 (pronto) |
| Analista Técnico | Tendência, entrada, alvo e stop | 2 (pronto) |
| Gestor de Risco | Aprova, ajusta ou veta sugestões | 2 (pronto) |
| Orquestrador e Conformidade | Plano do mês com as sugestões aprovadas | 2 (pronto) |
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

## Fase 2: Consultor, Analistas, Risco e Orquestrador

Referência inicial: R$ 10 mil e aporte de R$ 500 por mês.

```bash
inventidor plano --valor 10000 --aporte 500 --gastos 3000 --reserva 18000 --prazo 10 --perfil moderado
```

Sai, em ordem:

1. **Política do Consultor:** % por classe conforme perfil e prazo; reserva de emergência
   (6 meses de gastos) vem antes da bolsa; prazo abaixo de 2 anos fica todo em renda fixa.
2. **Plano de aportes mensais:** cada aporte compra a classe que está abaixo do alvo
   (rebalancear sem vender e sem gerar imposto). Não supõe rentabilidade.
3. **Plano do mês:** empresas aprovadas pelo Fundamentalista (lucro, dívida até 3x EBITDA,
   liquidez, nota mínima 5 e preço abaixo do justo), no momento certo pelo Técnico e dentro
   dos limites do Risco (até 20% da parte de ações por empresa, 40% por setor, perda até o
   stop de no máximo 2% do patrimônio, stop a no máximo 15%). Cada sugestão traz
   quantidade no fracionário, preço limite, stop, alvo, tese e parecer do Risco.
4. **Dicas de cada especialista.**

`exemplos/fundamentos.csv` e `exemplos/precos.csv` são **empresas fictícias com dados
sintéticos**, só para demonstrar. Para uso real, troque pelos indicadores e cotações das
empresas que você acompanha (a busca automática de dados é a próxima etapa).

Para conversar com a equipe (precisa de chave da API):

```bash
inventidor-equipe "Tenho 10 mil e aporto 500 por mês, perfil moderado. O que faço este mês?"
```

## Limitações conhecidas

- Feriados não entram no cálculo do vencimento (só fins de semana).
- Venda a descoberto, opções, subscrições, desdobramentos e bonificações ainda não são tratados.
- Dados de mercado entram por CSV; a busca automática (CVM, cotações) vem na próxima etapa.
- Leitura automática do PDF da nota de corretagem e do extrato da B3 vem na próxima etapa.
- Prejuízo em mês isento entra no saldo a compensar (`compensar_prejuizo_mes_isento`); confirme esse
  entendimento com seu contador.

## Aviso

Ferramenta de apoio à decisão para uso pessoal. Não é recomendação de investimento nem
substitui um contador. Confira os valores antes de pagar ou declarar.
