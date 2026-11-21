"""Gera exemplos/precos.csv: séries SINTÉTICAS de empresas fictícias, só para demonstração.

Uso: python scripts/gerar_precos_exemplo.py 0.01 0.001
"""
import math, datetime as dt, sys
amp, pb = float(sys.argv[1]), float(sys.argv[2])
perfis = {
  "ALFA3": (36.0, 0.0008, 42.0, "pullback"),
  "BETA4": (27.0, 0.0007, 31.5, "pullback"),
  "GAMA3": (28.0, 0.0010, 38.0, "pullback"),
  "DELT3": (66.0, -0.0009, 55.0, "baixa"),
  "ZETA3": (24.0, 0.0009, 29.0, "esticada"),
  "EPSI3": (16.0, -0.0012, 12.0, "baixa"),
  "ETAA4": (17.0, 0.0002, 18.0, "lateral"),
  "IOTA3": (17.0, 0.0008, 21.0, "pullback"),
  "KAPA3": (44.0, 0.0005, 48.0, "pullback"),
  "LAMB3": (12.0, 0.0009, 15.0, "pullback"),
}
d0 = dt.date(2025, 12, 1); dias=[]; d=d0
while len(dias) < 240:
    if d.weekday() < 5: dias.append(d)
    d += dt.timedelta(days=1)
linhas = ["data;ticker;fechamento;maxima;minima"]
for n,(t, (base, drift, final, tipo)) in enumerate(perfis.items()):
    serie = []
    for i in range(240):
        v = base * (1 + drift) ** i * (1 + amp * math.sin(i / 7.0 + 0.3 * n))
        if tipo == "esticada" and i > 220: v *= 1 + 0.01 * (i - 220)
        if tipo == "pullback" and i > 232: v *= 1 - pb * (i - 232)
        serie.append(v)
    k = final / serie[-1]
    for i, v in enumerate(serie):
        v *= k
        linhas.append(f"{dias[i]};{t};{v:.2f};{v*1.012:.2f};{v*0.988:.2f}")
open("exemplos/precos.csv", "w").write("\n".join(linhas) + "\n")
