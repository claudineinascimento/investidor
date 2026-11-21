"""Painel local para aprovar sugestões com um clique.

Roda só no seu computador (127.0.0.1), sem dependências além da biblioteca padrão.
Mostra a fila de decisões, a carteira e a boleta; aprovar, recusar e registrar
execução usam as mesmas regras do diário (nada pula etapa). Cada execução do
painel gera um token que os formulários precisam enviar, para que outro site
aberto no navegador não consiga aprovar nada por você.

    inventidor painel            # abre em http://127.0.0.1:8765
"""

from __future__ import annotations

import html
import secrets
import urllib.parse
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from inventidor import diario
from inventidor.carteira import Carteira
from inventidor.diario import ErroDiario, Estado
from inventidor.especialistas.mesa import boleta
from inventidor.importador import ler_csv
from inventidor.relatorio import AVISO_LEGAL

CSS = """
body{font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#1b1f24;background:#fff}
@media (prefers-color-scheme:dark){body{background:#14181d;color:#e6e9ee}.card{border-color:#3a424d}}
.card{border:1px solid #d0d7de;border-radius:8px;padding:12px 16px;margin:12px 0}
.tag{font-size:12px;border-radius:4px;padding:2px 6px;background:#8884}
button{font:inherit;padding:6px 12px;border-radius:6px;border:1px solid #8886;cursor:pointer}
pre{white-space:pre-wrap;background:#8882;padding:8px;border-radius:6px}
.aviso{font-size:13px;opacity:.75}.erro{color:#b42318}
"""


def _e(x) -> str:
    return html.escape(str(x))


class Painel:
    def __init__(self, diario_path: Path, operacoes_csv: Path):
        self.diario = diario_path
        self.operacoes = operacoes_csv
        self.token = secrets.token_urlsafe(16)

    def pagina(self, mensagem: str = "", erro: bool = False, boleta_id: str | None = None) -> str:
        itens = diario.carregar(self.diario)
        t = self.token
        partes = [f"<h1>Inventidor</h1><p class=aviso>{_e(AVISO_LEGAL)}</p>"]
        if mensagem:
            partes.append(f"<p class='{'erro' if erro else ''}'><b>{_e(mensagem)}</b></p>")
        partes.append("<h2>Fila de decisões</h2>")
        fila = [i for i in itens.values() if i.estado in (Estado.SUGERIDA, Estado.APROVADA)]
        if not fila:
            partes.append("<p>Nada pendente. Rode <code>inventidor plano --registrar</code> ou <code>inventidor vigiar --registrar</code>.</p>")
        for i in sorted(fila, key=lambda x: x.id):
            acao = "VENDER" if i.lado == "V" else "Comprar"
            lim = "a partir de" if i.lado == "V" else "a até"
            partes.append(
                f"<div class=card><span class=tag>{_e(i.estado.value)}</span> <b>{acao} {i.quantidade} {_e(i.ticker)}</b> "
                f"{lim} R$ {_e(i.preco_limite)} (R$ {i.valor:.2f})<br>"
                f"Stop R$ {_e(i.stop)} · Alvo R$ {_e(i.alvo)}<br><small>Tese: {_e(i.tese)}<br>Risco: {_e(i.parecer_risco)}</small><br>"
            )
            form = lambda acao_, rot, extra="": (
                f"<form method=post action=/{acao_} style='display:inline'>"
                f"<input type=hidden name=token value='{_e(t)}'><input type=hidden name=id value='{_e(i.id)}'>"
                f"{extra}<button>{rot}</button></form> "
            )
            if i.estado == Estado.SUGERIDA:
                partes.append(form("aprovar", "Aprovar"))
            else:
                partes.append(f"<a href='/?boleta={_e(i.id)}'><button type=button>Ver boleta</button></a> ")
                partes.append(form(
                    "executada", "Registrar execução",
                    "<input name=preco placeholder='preço R$' size=8 required> "
                    "<input name=custos placeholder='custos R$' size=8> ",
                ))
            partes.append(form("recusar", "Recusar", "<input name=motivo placeholder='motivo (opcional)'> "))
            partes.append("</div>")
        if boleta_id and boleta_id in itens:
            try:
                partes.append(f"<h2>Boleta</h2><pre>{_e(boleta(itens[boleta_id]))}</pre>")
            except ErroDiario as e:
                partes.append(f"<p class=erro>{_e(e)}</p>")
        partes.append("<h2>Carteira</h2>")
        try:
            pos = Carteira().processar(ler_csv(self.operacoes)).posicoes_abertas() if self.operacoes.exists() else []
        except ValueError as e:
            pos = []
            partes.append(f"<p class=erro>{_e(e)}</p>")
        if pos:
            linhas = "".join(
                f"<tr><td>{_e(p.ticker)}</td><td>{p.quantidade}</td><td>R$ {p.preco_medio:.2f}</td></tr>"
                for p in sorted(pos, key=lambda p: p.ticker)
            )
            partes.append(f"<table><tr><th>Ativo</th><th>Qtd</th><th>Preço médio</th></tr>{linhas}</table>")
        else:
            partes.append("<p>Sem posições abertas.</p>")
        corpo = "".join(partes)
        return (
            "<!doctype html><html lang=pt-BR><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>Inventidor</title><style>{CSS}</style><body>{corpo}</body></html>"
        )

    def agir(self, acao: str, campos: dict[str, str]) -> tuple[str, bool]:
        id_ = campos.get("id", "")
        try:
            if acao == "aprovar":
                diario.aprovar(id_, self.diario)
                return f"{id_} aprovada. Veja a boleta e envie na sua corretora.", False
            if acao == "recusar":
                diario.recusar(id_, campos.get("motivo", ""), self.diario)
                return f"{id_} recusada.", False
            if acao == "executada":
                num = lambda k: Decimal((campos.get(k) or "0").replace(",", "."))
                diario.executar(id_, num("preco"), custos=num("custos"),
                                operacoes_csv=self.operacoes, caminho=self.diario)
                return f"{id_} registrada. O Contador já considera a operação.", False
        except ErroDiario as e:
            return str(e), True
        except InvalidOperation:
            return "Preço ou custos inválidos.", True
        return "Ação desconhecida.", True


def criar_servidor(painel: Painel, porta: int = 8765) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def _enviar(self, corpo: str, status: int = 200):
            dados = corpo.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
            self.end_headers()
            self.wfile.write(dados)

        def _host_ok(self) -> bool:
            # Bloqueia DNS rebinding: só aceita acesso por localhost/127.0.0.1.
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self._host_ok():
                return self._enviar("Host não permitido.", 403)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._enviar(painel.pagina(boleta_id=(q.get("boleta") or [None])[0]))

        def do_POST(self):
            if not self._host_ok():
                return self._enviar("Host não permitido.", 403)
            n = int(self.headers.get("Content-Length") or 0)
            campos = {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}
            acao = self.path.strip("/")
            if not secrets.compare_digest(campos.get("token", ""), painel.token):
                return self._enviar("Token inválido.", 403)
            msg, erro = painel.agir(acao, campos)
            self._enviar(painel.pagina(msg, erro, boleta_id=campos.get("id") if acao == "aprovar" else None))

        def log_message(self, *a):  # silencioso
            pass

    return ThreadingHTTPServer(("127.0.0.1", porta), H)
