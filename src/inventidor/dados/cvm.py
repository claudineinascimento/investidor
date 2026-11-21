"""CVM: documentos periódicos e eventuais (IPE) das companhias abertas.

Arquivo anual: https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip
Dentro: ipe_cia_aberta_{ano}.csv, separado por ';', em latin-1.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date

from inventidor.dados.http import baixar

URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
COLUNAS = ("Nome_Companhia", "Categoria", "Tipo", "Assunto", "Data_Entrega", "Link_Download")


@dataclass(frozen=True)
class Documento:
    empresa: str
    cnpj: str
    data: date  # data de entrega à CVM
    categoria: str
    tipo: str
    assunto: str
    link: str


def _data(t: str) -> date | None:
    t = (t or "").strip()[:10]
    try:
        return date.fromisoformat(t)
    except ValueError:
        return None


def parse_ipe(texto: str) -> list[Documento]:
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
    if faltando:
        raise ValueError(f"Coluna ausente no arquivo IPE da CVM: {', '.join(faltando)}")
    docs = []
    for l in leitor:
        d = _data(l["Data_Entrega"])
        if d is None:
            continue
        docs.append(Documento(
            empresa=(l["Nome_Companhia"] or "").strip(), cnpj=(l.get("CNPJ_Companhia") or "").strip(), data=d,
            categoria=(l["Categoria"] or "").strip(), tipo=(l["Tipo"] or "").strip(),
            assunto=(l["Assunto"] or "").strip(), link=(l["Link_Download"] or "").strip(),
        ))
    return docs


def _texto_do_zip(bruto: bytes, ano: int) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(bruto))
    except zipfile.BadZipFile as e:
        raise ValueError(f"CVM devolveu algo que não é ZIP para {ano}: {bruto[:200]!r}") from e
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    if not nomes:
        raise ValueError(f"ZIP do IPE {ano} não tem CSV: {z.namelist()}")
    bruto_csv = z.read(nomes[0])
    try:
        return bruto_csv.decode("utf-8-sig")
    except UnicodeDecodeError:
        return bruto_csv.decode("latin-1")


def baixar_ipe(ano: int) -> list[Documento]:
    return parse_ipe(_texto_do_zip(baixar(URL.format(ano=ano), validade=3 * 3600, timeout=180), ano))


def baixar_ipe_desde(desde: date, ate: date | None = None) -> list[Documento]:
    """Baixa os anos necessários para cobrir de `desde` até hoje (ex.: janela que cruza o ano)."""
    ate = ate or date.today()
    docs: list[Documento] = []
    for ano in range(desde.year, ate.year + 1):
        docs += baixar_ipe(ano)
    return docs
