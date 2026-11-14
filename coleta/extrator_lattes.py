"""Importa currículos no formato XML do Lattes (Extrator Lattes / CNPq).

O CNPq só fornece currículos em massa pelo Extrator Lattes, a instituições
conveniadas. Este script NÃO baixa nada do site do Lattes: ele lê arquivos XML
(ou .zip contendo XML) que você já recebeu legitimamente, mantém só quem tem
endereço profissional no RJ e funde os dados com os do OpenAlex (pelo ORCID).

Uso:
    python coleta/extrator_lattes.py pasta_com_xmls/ [outro_arquivo.zip ...]
"""

import argparse
import hashlib
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import atualizar_meta, gravar_json, ler_json  # noqa: E402

UF = "RJ"


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def ler_arquivos(caminhos):
    """Gera (nome, bytes) de cada XML encontrado em pastas, .xml e .zip."""
    for c in caminhos:
        if os.path.isdir(c):
            for raiz, _, arquivos in os.walk(c):
                for a in sorted(arquivos):
                    yield from ler_arquivos([os.path.join(raiz, a)])
        elif c.lower().endswith(".zip"):
            with zipfile.ZipFile(c) as z:
                for n in z.namelist():
                    if n.lower().endswith(".xml"):
                        yield n, z.read(n)
        elif c.lower().endswith(".xml"):
            with open(c, "rb") as f:
                yield c, f.read()


def contar_producao(raiz):
    prod = raiz.find("PRODUCAO-BIBLIOGRAFICA")
    if prod is None:
        return 0
    total = 0
    for grupo in prod:  # ARTIGOS-PUBLICADOS, LIVROS-E-CAPITULOS, ...
        for item in grupo.iter():
            if item is not grupo and any(f.tag.startswith("DADOS-BASICOS") for f in item):
                total += 1
    return total


class Casador:
    """Liga o nome da instituição escrito no Lattes a uma instituição do OpenAlex."""

    def __init__(self, instituicoes):
        self.por_chave = {}
        for i in instituicoes:
            for chave in (i["nome"], i.get("sigla")):
                if chave:
                    self.por_chave.setdefault(normalizar(chave), i["id"])

    def __call__(self, nome, sigla=None):
        for chave in (nome, sigla):
            n = normalizar(chave)
            if n in self.por_chave:
                return self.por_chave[n]
        return None


def ler_curriculo(conteudo, casar):
    raiz = ET.fromstring(conteudo)
    if raiz.tag != "CURRICULO-VITAE":
        return None
    gerais = raiz.find("DADOS-GERAIS")
    if gerais is None:
        return None
    end = gerais.find("ENDERECO/ENDERECO-PROFISSIONAL")
    if end is None or (end.get("UF") or "").upper() != UF:
        return None

    nome_inst = end.get("NOME-INSTITUICAO-EMPRESA") or ""
    inst = casar(nome_inst)
    unidade = " / ".join(x for x in (end.get("NOME-ORGAO"), end.get("NOME-UNIDADE")) if x) or None

    areas = []
    for a in gerais.iter("AREA-DE-ATUACAO"):
        areas.append(((a.get("NOME-GRANDE-AREA-DO-CONHECIMENTO") or "").replace("_", " ").title(),
                      a.get("NOME-DA-AREA-DO-CONHECIMENTO") or ""))
    grande, area = areas[0] if areas else ("", "")

    linhas = {}
    for lp in raiz.iter("LINHA-DE-PESQUISA"):
        titulo = (lp.get("TITULO-DA-LINHA-DE-PESQUISA") or "").strip()
        if titulo:
            lid = "LL" + hashlib.sha1(normalizar(titulo).encode()).hexdigest()[:10]
            linhas[lid] = {"nome": titulo, "area": area or None, "grande_area": grande or None}

    numero = raiz.get("NUMERO-IDENTIFICADOR")
    orcid = (gerais.get("ORCID-ID") or "").rsplit("/", 1)[-1] or None
    pesquisador = {
        "id": f"L{numero}",
        "n": gerais.get("NOME-COMPLETO"),
        "o": orcid,
        "l": numero,
        "i": [inst] if inst else [],
        "u": unidade,
        "ie": None if inst else nome_inst or None,  # instituição sem correspondência no mapa
        "p": contar_producao(raiz),
        "c": None,
        "h": None,
        "t": list(linhas)[:10],
        "f": "lattes",
        "atualizado": raiz.get("DATA-ATUALIZACAO"),
    }
    return pesquisador, linhas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+", help="pastas, arquivos .xml ou .zip")
    args = ap.parse_args()

    instituicoes = ler_json("instituicoes.json", []) or []
    casar = Casador(instituicoes)
    linhas = ler_json("linhas.json", {}) or {}
    existentes = ler_json("pesquisadores.json", []) or []
    por_orcid = {p["o"]: p for p in existentes if p.get("o") and p.get("f") == "openalex"}
    por_id = {p["id"]: p for p in existentes}

    lidos = rj = 0
    for nome, conteudo in ler_arquivos(args.caminhos):
        lidos += 1
        try:
            r = ler_curriculo(conteudo, casar)
        except ET.ParseError as e:
            print(f"  aviso: {nome} não é um XML válido ({e})")
            continue
        if not r:
            continue
        p, novas = r
        rj += 1
        linhas.update(novas)
        oa = por_orcid.pop(p["o"], None) if p["o"] else None
        if oa:  # mesma pessoa no OpenAlex: Lattes vira o registro principal
            por_id.pop(oa["id"], None)
            p["oa"] = oa["id"]
            p["c"], p["h"] = oa["c"], oa["h"]
            p["p"] = max(p["p"], oa["p"])
            p["i"] = sorted(set(p["i"]) | set(oa["i"]))
        por_id[p["id"]] = p

    pesquisadores = list(por_id.values())
    contagem = {}
    for p in pesquisadores:
        for i in p["i"]:
            contagem[i] = contagem.get(i, 0) + 1
    for inst in instituicoes:
        inst["pesquisadores"] = contagem.get(inst["id"], 0)

    gravar_json("pesquisadores.json", pesquisadores)
    gravar_json("linhas.json", linhas)
    gravar_json("instituicoes.json", instituicoes)
    atualizar_meta("lattes", curriculos_lidos=lidos, curriculos_rj=rj)
    print(f"Pronto: {lidos} currículos lidos, {rj} com endereço profissional no RJ.")


if __name__ == "__main__":
    main()
