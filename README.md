# Pesquisa no RJ: dados abertos de pesquisadores, laboratórios e linhas de pesquisa

Plataforma gratuita para consultar **pesquisadores, laboratórios/institutos e linhas
de pesquisa do estado do Rio de Janeiro**, com filtros e um **mapa** por instituição.

O site fica na pasta [`docs/`](docs/) e roda no GitHub Pages, sem servidor.
Os dados ficam em [`docs/dados/`](docs/dados/) e podem ser baixados direto, em JSON,
ou pelo botão "Baixar CSV" no site.

## Licença e créditos

Este repositório (código **e** dados processados) está sob a licença
**[Creative Commons Atribuição-NãoComercial 4.0 Internacional (CC BY-NC 4.0)](LICENSE)**.

- ✅ Você pode copiar, adaptar e redistribuir **gratuitamente**.
- ❌ **Não pode usar para fins comerciais**, ou seja, para obter ganho financeiro.
- ✍️ **Deve dar crédito** a este repositório. Sugestão de citação:

  > Dados e código de *Pesquisa no RJ*, https://github.com/Irving-Merath/Lattes (CC BY-NC 4.0).

Os dados de origem do OpenAlex são CC0 (domínio público). Os currículos Lattes
pertencem aos seus titulares e ao CNPq. Aqui são publicados só dados profissionais
públicos e processados, nunca os XMLs brutos.

## De onde vêm os dados

| Fonte | O que traz | Como entra |
|---|---|---|
| [OpenAlex](https://openalex.org) | Instituições do RJ (com coordenadas), pesquisadores que publicam, temas de pesquisa, publicações, citações, índice h e ORCID | Automático, todo mês ([`coleta/openalex_rj.py`](coleta/openalex_rj.py)) |
| Extrator Lattes (CNPq) | Currículo completo: ID Lattes, unidade/laboratório, linhas de pesquisa declaradas | Manual, a partir de XMLs recebidos por convênio ([`coleta/extrator_lattes.py`](coleta/extrator_lattes.py)) |

**Por que não se baixa direto do site do Lattes?** As páginas de currículo têm CAPTCHA
e os termos de uso do CNPq proíbem a coleta automatizada em massa. O acesso em massa
oficial é o **Extrator Lattes**, liberado a instituições conveniadas com o CNPq. Este
projeto não contorna essas proteções. Quando houver XMLs do Extrator, o importador
os funde aos dados do OpenAlex, usando o ORCID para identificar a mesma pessoa.

### Limitações conhecidas

- O OpenAlex só inclui quem publica. O padrão é listar pesquisadores com **10 ou mais
  publicações**, valor ajustável com `--min-publicacoes`.
- A instituição de cada pesquisador é a "última instituição conhecida" segundo o OpenAlex.
  Ela pode estar desatualizada ou errada, especialmente em nomes muito comuns.
- As linhas de pesquisa do OpenAlex são temas atribuídos automaticamente, com nomes
  em inglês. As linhas vindas do Lattes são as declaradas pelo próprio pesquisador.
- Algumas instituições têm coordenadas aproximadas (o centro da cidade sede).
- "Laboratórios" aqui são institutos e unidades cadastrados no OpenAlex, por exemplo o
  IOC dentro da Fiocruz, além das unidades informadas no Lattes. Grupos do
  [Diretório dos Grupos de Pesquisa (DGP/CNPq)](https://dgp.cnpq.br) ainda não estão
  incluídos (veja o roteiro abaixo).

## Como usar

### Ver o site localmente

```bash
cd docs
python3 -m http.server 8000
# abra http://localhost:8000
```

### Atualizar os dados do OpenAlex

Crie uma chave gratuita em https://openalex.org/settings/api e rode:

```bash
OPENALEX_API_KEY=suachave python3 coleta/openalex_rj.py --min-publicacoes 10
```

No GitHub, o workflow [`Atualizar dados`](.github/workflows/coleta.yml) faz isso todo
mês, usando o segredo `OPENALEX_API_KEY` (Settings → Secrets and variables → Actions).

### Importar currículos do Extrator Lattes

```bash
python3 coleta/extrator_lattes.py pasta_com_xmls/   # aceita .xml e .zip
```

O script lê só currículos com endereço profissional no RJ. Ele grava em `docs/dados/`
apenas nome, ID Lattes, ORCID, instituição, unidade, linhas de pesquisa e total de
produção. **Não suba os XMLs para o repositório**: eles contêm dados pessoais. A pasta
`lattes_xml/` já está no `.gitignore`.

### Publicar no GitHub Pages

Settings → Pages → *Deploy from a branch* → branch `main`, pasta `/docs`.

### Testes

```bash
pip install pytest
python3 -m pytest testes
```

## Estrutura

```
coleta/            scripts de coleta e importação (Python, sem dependências externas)
docs/              site estático (GitHub Pages)
  dados/           dados processados (JSON)
testes/            testes automatizados, com um currículo XML fictício
.github/workflows/ atualização mensal automática
```

## Roteiro

- [x] Instituições, pesquisadores e linhas de pesquisa do RJ (OpenAlex)
- [x] Mapa por instituição, filtros, exportação em CSV, links compartilháveis
- [x] Importador de currículos do Extrator Lattes
- [ ] Grupos de pesquisa e linhas do DGP/CNPq
- [ ] Tradução dos nomes das linhas de pesquisa para o português
- [ ] Outros estados
