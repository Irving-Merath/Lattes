"""Funções e esquema de dados compartilhados pelos coletores.

Todos os coletores gravam no mesmo formato, em docs/dados/:

  instituicoes.json  lista de instituições/laboratórios com coordenadas
  pesquisadores.json lista de pesquisadores (chaves curtas para reduzir tamanho)
  linhas.json        dicionário de linhas de pesquisa (temas)
  meta.json          data da coleta, fontes e totais

Chaves de cada pesquisador em pesquisadores.json:
  id  identificador interno (OpenAlex "A123" ou Lattes "L1234567890123456")
  n   nome
  o   ORCID (ou null)
  l   ID Lattes de 16 dígitos (ou null)
  i   lista de IDs de instituições (ver instituicoes.json)
  p   número de publicações
  c   número de citações
  h   índice h (ou null)
  t   lista de IDs de linhas de pesquisa (ver linhas.json)
  f   fonte dos dados ("openalex", "lattes")
"""

import json
import os
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_DADOS = os.path.join(RAIZ, "docs", "dados")

# Tradução das grandes áreas e áreas do OpenAlex (domains/fields).
GRANDES_AREAS = {
    "Life Sciences": "Ciências da Vida",
    "Social Sciences": "Ciências Sociais",
    "Physical Sciences": "Ciências Exatas e da Terra",
    "Health Sciences": "Ciências da Saúde",
}

AREAS = {
    "Agricultural and Biological Sciences": "Ciências Agrárias e Biológicas",
    "Arts and Humanities": "Artes e Humanidades",
    "Biochemistry, Genetics and Molecular Biology": "Bioquímica, Genética e Biologia Molecular",
    "Business, Management and Accounting": "Administração e Contabilidade",
    "Chemical Engineering": "Engenharia Química",
    "Chemistry": "Química",
    "Computer Science": "Ciência da Computação",
    "Decision Sciences": "Ciências da Decisão",
    "Dentistry": "Odontologia",
    "Earth and Planetary Sciences": "Geociências",
    "Economics, Econometrics and Finance": "Economia",
    "Energy": "Energia",
    "Engineering": "Engenharias",
    "Environmental Science": "Ciências Ambientais",
    "Health Professions": "Profissões da Saúde",
    "Immunology and Microbiology": "Imunologia e Microbiologia",
    "Materials Science": "Ciência dos Materiais",
    "Mathematics": "Matemática",
    "Medicine": "Medicina",
    "Neuroscience": "Neurociências",
    "Nursing": "Enfermagem",
    "Pharmacology, Toxicology and Pharmaceutics": "Farmacologia e Toxicologia",
    "Physics and Astronomy": "Física e Astronomia",
    "Psychology": "Psicologia",
    "Social Sciences": "Ciências Sociais Aplicadas",
    "Veterinary": "Medicina Veterinária",
}

TIPOS_INSTITUICAO = {
    "education": "Ensino superior",
    "facility": "Instituto / laboratório",
    "healthcare": "Saúde",
    "government": "Governo",
    "nonprofit": "Sem fins lucrativos",
    "company": "Empresa",
    "archive": "Arquivo / museu",
    "funder": "Agência de fomento",
    "other": "Outro",
}


def caminho(nome):
    return os.path.join(DIR_DADOS, nome)


def ler_json(nome, padrao=None):
    try:
        with open(caminho(nome), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return padrao


def gravar_json(nome, dados):
    os.makedirs(DIR_DADOS, exist_ok=True)
    with open(caminho(nome), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))


def agora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def id_curto(url):
    """https://openalex.org/I123 -> I123"""
    return url.rsplit("/", 1)[-1] if url else None


def orcid_curto(url):
    """https://orcid.org/0000-0002-... -> 0000-0002-..."""
    return url.rsplit("/", 1)[-1] if url else None


def atualizar_meta(fonte, **info):
    meta = ler_json("meta.json", {}) or {}
    meta.setdefault("fontes", {})[fonte] = {"atualizado_em": agora_iso(), **info}
    pesquisadores = ler_json("pesquisadores.json", []) or []
    meta["totais"] = {
        "instituicoes": len(ler_json("instituicoes.json", []) or []),
        "pesquisadores": len(pesquisadores),
        "linhas": len(ler_json("linhas.json", {}) or {}),
    }
    meta["licenca"] = "CC BY-NC 4.0"
    meta["repositorio"] = "https://github.com/Irving-Merath/Lattes"
    gravar_json("meta.json", meta)
