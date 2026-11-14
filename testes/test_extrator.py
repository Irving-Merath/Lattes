import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "coleta"))
from extrator_lattes import Casador, ler_curriculo  # noqa: E402

EXEMPLO = os.path.join(os.path.dirname(__file__), "exemplos", "curriculo_ficticio.xml")


def test_le_curriculo_ficticio():
    casar = Casador([{"id": "I1", "nome": "Universidade Federal Fluminense", "sigla": "UFF"}])
    with open(EXEMPLO, "rb") as f:
        p, linhas = ler_curriculo(f.read(), casar)
    assert p["l"] == "0000000000000001"
    assert p["n"] == "Pessoa Fictícia de Teste"
    assert p["o"] == "0000-0000-0000-0000"
    assert p["i"] == ["I1"]
    assert p["u"] == "Instituto de Física / Laboratório de Exemplo"
    assert p["p"] == 2
    assert [v["nome"] for v in linhas.values()] == ["Física de materiais de teste"]


def test_ignora_fora_do_rj():
    with open(EXEMPLO, "rb") as f:
        xml = f.read().replace(b'UF="RJ"', b'UF="SP"')
    assert ler_curriculo(xml, Casador([])) is None
