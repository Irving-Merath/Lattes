"""Coleta instituições, pesquisadores e linhas de pesquisa do estado do RJ no OpenAlex.

O OpenAlex (https://openalex.org) é uma base aberta (CC0) de produção científica.
Não substitui o Lattes, mas cobre os pesquisadores que publicam e permite ligar
cada um ao seu ORCID, que muitas vezes também aparece no currículo Lattes.

Uso:
    OPENALEX_API_KEY=suachave python coleta/openalex_rj.py [--min-publicacoes 10]

A chave é gratuita (https://openalex.org/settings/api). Sem chave, a API usa
uma cota diária compartilhada e pode recusar as consultas.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import (  # noqa: E402
    AREAS,
    GRANDES_AREAS,
    TIPOS_INSTITUICAO,
    atualizar_meta,
    gravar_json,
    id_curto,
    ler_json,
    orcid_curto,
)

API = "https://api.openalex.org"
ESTADO = "Rio de Janeiro"
LOTE_INSTITUICOES = 50  # quantos IDs de instituição por consulta de autores


def consultar(caminho, params, tentativas=5):
    chave = os.environ.get("OPENALEX_API_KEY")
    url = f"{API}/{caminho}?{urllib.parse.urlencode(params, safe=':|>,*')}"
    req = urllib.request.Request(url, headers={"User-Agent": "lattes-rj-dados-abertos"})
    if chave:
        req.add_header("Authorization", f"Bearer {chave}")
    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentativa < tentativas - 1:
                time.sleep(2 ** tentativa * 3)
                continue
            raise SystemExit(f"Erro {e.code} em {url}: {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError):
            if tentativa < tentativas - 1:
                time.sleep(2 ** tentativa * 3)
                continue
            raise


def paginar(caminho, params):
    cursor = "*"
    while cursor:
        dados = consultar(caminho, {**params, "per_page": 200, "cursor": cursor})
        yield from dados["results"]
        cursor = dados["meta"].get("next_cursor")


def coletar_instituicoes():
    campos = "id,display_name,display_name_acronyms,ror,geo,type,lineage,works_count,homepage_url"
    rj = []
    for r in paginar("institutions", {"filter": "country_code:BR", "select": campos}):
        geo = r.get("geo") or {}
        if geo.get("region") != ESTADO or geo.get("latitude") is None:
            continue
        linhagem = [id_curto(x) for x in r.get("lineage") or []]
        proprio = id_curto(r["id"])
        pai = next((x for x in linhagem if x != proprio), None)
        rj.append(
            {
                "id": proprio,
                "nome": r["display_name"],
                "sigla": (r.get("display_name_acronyms") or [None])[0],
                "tipo": TIPOS_INSTITUICAO.get(r.get("type"), "Outro"),
                "laboratorio": bool(pai) or r.get("type") == "facility",
                "pai": pai,
                "cidade": geo.get("city"),
                "lat": round(geo["latitude"], 5),
                "lon": round(geo["longitude"], 5),
                "ror": r.get("ror"),
                "site": r.get("homepage_url"),
                "publicacoes": r.get("works_count", 0),
            }
        )
    return rj


def coletar_pesquisadores(instituicoes, min_publicacoes):
    ids_rj = {i["id"] for i in instituicoes}
    lista = sorted(ids_rj)
    campos = "id,display_name,orcid,works_count,cited_by_count,summary_stats,topics,last_known_institutions"
    pesquisadores = {}
    linhas = {}
    for k in range(0, len(lista), LOTE_INSTITUICOES):
        lote = "|".join(lista[k : k + LOTE_INSTITUICOES])
        filtro = f"last_known_institutions.id:{lote},works_count:>{min_publicacoes - 1}"
        for a in paginar("authors", {"filter": filtro, "select": campos}):
            aid = id_curto(a["id"])
            if aid in pesquisadores:
                continue
            insts = [id_curto(x["id"]) for x in a.get("last_known_institutions") or []]
            insts = [x for x in insts if x in ids_rj]
            temas = []
            for t in (a.get("topics") or [])[:3]:
                tid = id_curto(t["id"])
                temas.append(tid)
                if tid not in linhas:
                    area = (t.get("field") or {}).get("display_name")
                    grande = (t.get("domain") or {}).get("display_name")
                    linhas[tid] = {
                        "nome": t["display_name"],
                        "area": AREAS.get(area, area),
                        "grande_area": GRANDES_AREAS.get(grande, grande),
                    }
            pesquisadores[aid] = {
                "id": aid,
                "n": a["display_name"],
                "o": orcid_curto(a.get("orcid")),
                "l": None,
                "i": insts,
                "p": a.get("works_count", 0),
                "c": a.get("cited_by_count", 0),
                "h": (a.get("summary_stats") or {}).get("h_index"),
                "t": temas,
                "f": "openalex",
            }
        print(f"  instituições {k + 1}-{min(k + LOTE_INSTITUICOES, len(lista))}: "
              f"{len(pesquisadores)} pesquisadores até agora", flush=True)
    return list(pesquisadores.values()), linhas


def resumir_instituicoes(instituicoes, pesquisadores, linhas):
    """Conta pesquisadores e as principais linhas de pesquisa de cada instituição."""
    contagem = Counter()
    temas = defaultdict(Counter)
    for p in pesquisadores:
        for i in p["i"]:
            contagem[i] += 1
            temas[i].update(p["t"])
    for inst in instituicoes:
        inst["pesquisadores"] = contagem[inst["id"]]
        inst["linhas"] = [t for t, _ in temas[inst["id"]].most_common(8) if t in linhas]
    return instituicoes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-publicacoes", type=int, default=10,
                    help="ignora autores com menos publicações (padrão: 10)")
    args = ap.parse_args()

    print("Coletando instituições do RJ...", flush=True)
    instituicoes = coletar_instituicoes()
    print(f"  {len(instituicoes)} instituições", flush=True)

    print("Coletando pesquisadores...", flush=True)
    novos, linhas = coletar_pesquisadores(instituicoes, args.min_publicacoes)

    # Mantém pesquisadores de outras fontes (ex.: Extrator Lattes) já gravados.
    outros = [p for p in ler_json("pesquisadores.json", []) or [] if p.get("f") != "openalex"]
    linhas = {**(ler_json("linhas.json", {}) or {}), **linhas}
    orcids_lattes = {p["o"]: p for p in outros if p.get("o")}
    pesquisadores = list(outros)
    for p in novos:
        existente = orcids_lattes.get(p["o"]) if p["o"] else None
        if existente:  # mesmo ORCID já veio do Lattes: completa as métricas
            existente.update({k: p[k] for k in ("p", "c", "h") if existente.get(k) in (None, 0)})
            existente["i"] = sorted(set(existente["i"]) | set(p["i"]))
            existente["t"] = existente["t"] or p["t"]
            existente["oa"] = p["id"]
        else:
            pesquisadores.append(p)

    instituicoes = resumir_instituicoes(instituicoes, pesquisadores, linhas)
    gravar_json("instituicoes.json", instituicoes)
    gravar_json("pesquisadores.json", pesquisadores)
    gravar_json("linhas.json", linhas)
    atualizar_meta("openalex", min_publicacoes=args.min_publicacoes, url="https://openalex.org",
                   licenca_fonte="CC0")
    print(f"Pronto: {len(instituicoes)} instituições, {len(pesquisadores)} pesquisadores, "
          f"{len(linhas)} linhas de pesquisa.")


if __name__ == "__main__":
    main()
