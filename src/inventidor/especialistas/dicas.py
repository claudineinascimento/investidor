"""Dicas de cada especialista, mostradas no plano do mês."""

DICAS: dict[str, list[str]] = {
    "Consultor": [
        "Reserva de emergência primeiro: 6 meses de gastos em renda fixa com liquidez diária.",
        "Aporte todo mês no mesmo dia, como uma conta fixa. A constância pesa mais que acertar o momento.",
        "Rebalanceie com os aportes: compre o que ficou abaixo do alvo, em vez de vender o que subiu.",
        "Só coloque na bolsa dinheiro que pode ficar lá por 5 anos ou mais.",
    ],
    "Analista Fundamentalista": [
        "Prefira empresas com lucro consistente, dívida controlada e ROE acima de 15%.",
        "Dividend yield alto num ano só pode ser um evento pontual: olhe a média de 5 anos.",
        "Preço justo é uma faixa, não um número exato. Exija margem de segurança.",
        "Leia o release de resultados de cada empresa da carteira todo trimestre.",
    ],
    "Analista Técnico": [
        "Defina o stop antes de comprar e anote. Depois da compra, a emoção atrapalha.",
        "Evite comprar ações muito esticadas acima da média de 20 dias.",
        "Para quem investe no longo prazo, a análise técnica serve para escolher o momento, não a empresa.",
    ],
    "Gestor de Risco": [
        "Nenhuma ação deve pesar mais de 20% da parte de ações; nenhum setor mais de 40%.",
        "Cada operação pode perder no máximo 2% do patrimônio se o stop for atingido.",
        "Com R$ 10 mil, 5 a 8 ações já trazem boa diversificação; mais que isso vira trabalho sem ganho.",
    ],
    "Contador": [
        "Vendas de ações até R$ 20 mil no mês são isentas, mas o lucro precisa ser declarado.",
        "Guarde todas as notas de corretagem: são a prova do seu preço médio.",
        "Prejuízo também se declara: ele abate lucros futuros e reduz o imposto.",
        "DARF vence no último dia útil do mês seguinte; atraso gera multa e juros.",
    ],
    "Mesa": [
        "Use ordem limitada, nunca a mercado, para não pagar mais caro em ações com pouco volume.",
        "Abaixo de 100 ações, compre no mercado fracionário (ticker com F no final).",
        "Muitas corretoras zeraram a corretagem: confira as taxas da sua antes de fazer muitas ordens pequenas.",
    ],
}
