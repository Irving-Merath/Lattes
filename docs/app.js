// Plataforma de dados abertos de pesquisa do RJ.
// Licença CC BY-NC 4.0 — https://github.com/Irving-Merath/Lattes
"use strict";

const POR_PAGINA = 50;
const estado = { aba: "mapa", pagina: 0, ordem: "c", desc: true, filtrados: [] };
let INST = [], PESQ = [], LINHAS = {}, instPorId = {};
let mapa, camada;

const $ = (id) => document.getElementById(id);
const fmt = (n) => (n == null ? "–" : n.toLocaleString("pt-BR"));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

async function carregar() {
  const ler = (n) => fetch(`dados/${n}`).then((r) => { if (!r.ok) throw new Error(n); return r.json(); });
  const [inst, pesq, linhas, meta] = await Promise.all(
    ["instituicoes.json", "pesquisadores.json", "linhas.json", "meta.json"].map(ler));
  INST = inst; PESQ = pesq; LINHAS = linhas;
  instPorId = Object.fromEntries(INST.map((i) => [i.id, i]));
  for (const p of PESQ) {
    const nomesInst = p.i.map((i) => instPorId[i]?.nome + " " + (instPorId[i]?.sigla || "")).join(" ");
    const nomesLinhas = p.t.map((t) => LINHAS[t]?.nome || "").join(" ");
    p._busca = norm(`${p.n} ${nomesInst} ${p.ie || ""} ${p.u || ""} ${nomesLinhas}`);
    p._linhas = norm(nomesLinhas);
  }
  const datas = Object.values(meta.fontes || {}).map((f) => f.atualizado_em).sort();
  $("totais").textContent = `${fmt(meta.totais.pesquisadores)} pesquisadores · ${fmt(meta.totais.instituicoes)} instituições · ` +
    `${fmt(meta.totais.linhas)} linhas · atualizado em ${datas.length ? new Date(datas.at(-1)).toLocaleDateString("pt-BR") : "–"}`;
  montarFiltros();
  if (window.L) montarMapa();
  else $("mapa").textContent = "Não foi possível carregar o mapa. As abas de pesquisadores, instituições e linhas continuam funcionando.";
  lerFiltrosDaUrl();
  atualizar();
}

function opcoes(sel, valores) {
  for (const v of [...new Set(valores.filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"))) {
    sel.add(new Option(v, v));
  }
}

function montarFiltros() {
  const linhas = Object.values(LINHAS);
  opcoes($("f-grande"), linhas.map((l) => l.grande_area));
  opcoes($("f-area"), linhas.map((l) => l.area));
  opcoes($("f-cidade"), INST.map((i) => i.cidade));
  opcoes($("f-tipo"), INST.map((i) => i.tipo));
  const comPesq = INST.filter((i) => i.pesquisadores > 0).sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  for (const i of comPesq) $("f-inst").add(new Option(i.sigla ? `${i.nome} (${i.sigla})` : i.nome, i.id));
  const dl = $("lista-linhas");
  for (const l of linhas.slice(0, 3000)) dl.append(new Option(l.nome));

  for (const id of ["f-texto", "f-linha", "f-min"]) $(id).addEventListener("input", debounce(() => { estado.pagina = 0; atualizar(); }, 200));
  for (const id of ["f-grande", "f-area", "f-cidade", "f-inst", "f-tipo", "f-lab"]) $(id).addEventListener("change", () => { estado.pagina = 0; atualizar(); });
  $("limpar").addEventListener("click", () => {
    for (const id of ["f-texto", "f-linha", "f-grande", "f-area", "f-cidade", "f-inst", "f-tipo"]) $(id).value = "";
    $("f-min").value = 0; $("f-lab").checked = false; estado.pagina = 0; atualizar();
  });
  document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => trocarAba(b.dataset.aba)));
  document.querySelectorAll("th[data-ord]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.ord;
    estado.desc = estado.ordem === k ? !estado.desc : k !== "n";
    estado.ordem = k; estado.pagina = 0; desenharPesquisadores();
  }));
  $("baixar").addEventListener("click", baixarCsv);
  // Clique numa etiqueta de linha de pesquisa filtra por ela.
  document.addEventListener("click", (e) => {
    const linha = e.target.closest("[data-linha]");
    if (linha) { $("f-linha").value = linha.dataset.linha; estado.pagina = 0; trocarAba("pesquisadores"); atualizar(); }
    const inst = e.target.closest("[data-inst]");
    if (inst) { $("f-inst").value = inst.dataset.inst; estado.pagina = 0; trocarAba("pesquisadores"); atualizar(); }
  });
}

function trocarAba(aba) {
  estado.aba = aba;
  document.querySelectorAll(".abas button").forEach((b) => b.setAttribute("aria-selected", b.dataset.aba === aba));
  for (const a of ["mapa", "pesquisadores", "instituicoes", "linhas"]) $(`aba-${a}`).hidden = a !== aba;
  if (aba === "mapa") setTimeout(() => mapa.invalidateSize(), 0);
}

function filtros() {
  return {
    texto: norm($("f-texto").value.trim()),
    linha: norm($("f-linha").value.trim()),
    grande: $("f-grande").value, area: $("f-area").value,
    cidade: $("f-cidade").value, inst: $("f-inst").value, tipo: $("f-tipo").value,
    lab: $("f-lab").checked, min: Number($("f-min").value) || 0,
  };
}

function instituicaoPassa(i, f) {
  if (!i) return false;
  if (f.cidade && i.cidade !== f.cidade) return false;
  if (f.tipo && i.tipo !== f.tipo) return false;
  if (f.lab && !i.laboratorio) return false;
  if (f.inst && i.id !== f.inst && i.pai !== f.inst) return false;
  return true;
}

function pesquisadorPassa(p, f, instOk) {
  if (f.min && (p.p || 0) < f.min) return false;
  if (f.texto && !p._busca.includes(f.texto)) return false;
  if (f.linha && !p._linhas.includes(f.linha)) return false;
  if (f.grande && !p.t.some((t) => LINHAS[t]?.grande_area === f.grande)) return false;
  if (f.area && !p.t.some((t) => LINHAS[t]?.area === f.area)) return false;
  const filtraInst = f.cidade || f.tipo || f.lab || f.inst;
  if (filtraInst && !p.i.some((i) => instOk.has(i))) return false;
  return true;
}

function atualizar() {
  const f = filtros();
  const instOk = new Set(INST.filter((i) => instituicaoPassa(i, f)).map((i) => i.id));
  estado.filtrados = PESQ.filter((p) => pesquisadorPassa(p, f, instOk));
  estado.contagem = {};
  estado.temas = {};
  for (const p of estado.filtrados) {
    for (const i of p.i) if (instOk.has(i)) estado.contagem[i] = (estado.contagem[i] || 0) + 1;
    for (const t of p.t) estado.temas[t] = (estado.temas[t] || 0) + 1;
  }
  estado.instOk = instOk;
  escreverFiltrosNaUrl(f);
  desenharMapa();
  desenharPesquisadores();
  desenharInstituicoes();
  desenharLinhas();
}

function montarMapa() {
  mapa = L.map("mapa", { preferCanvas: true }).setView([-22.4, -42.9], 8);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa);
  camada = L.layerGroup().addTo(mapa);
}

function desenharMapa() {
  if (!camada) return;
  camada.clearLayers();
  const cor = getComputedStyle(document.documentElement).getPropertyValue("--destaque").trim() || "#0b6e6e";
  const lista = INST.filter((i) => estado.contagem[i.id]).sort((a, b) => estado.contagem[b.id] - estado.contagem[a.id]);
  for (const i of lista) {
    const n = estado.contagem[i.id];
    const raio = 3 + Math.sqrt(n) * 0.45;
    const linhas = (i.linhas || []).slice(0, 5).map((t) => LINHAS[t]?.nome).filter(Boolean);
    L.circleMarker([i.lat, i.lon], { radius: raio, color: cor, weight: 1, fillColor: cor, fillOpacity: 0.35 })
      .bindPopup(`<h3>${esc(i.nome)}${i.sigla ? ` (${esc(i.sigla)})` : ""}</h3>
        ${esc(i.tipo)} · ${esc(i.cidade || "")}<br>
        <strong>${fmt(n)}</strong> pesquisadores com os filtros atuais<br>
        ${linhas.length ? `<em>Principais linhas:</em> ${linhas.map(esc).join("; ")}<br>` : ""}
        <a href="#" data-inst="${esc(i.id)}">Ver pesquisadores</a>
        ${i.site ? ` · <a href="${esc(i.site)}" target="_blank" rel="noopener">site</a>` : ""}`)
      .addTo(camada);
  }
}

function ordenar(lista) {
  const k = estado.ordem, s = estado.desc ? -1 : 1;
  return lista.slice().sort((a, b) => k === "n"
    ? s * a.n.localeCompare(b.n, "pt-BR")
    : s * ((a[k] ?? -1) - (b[k] ?? -1)));
}

function nomeInst(p) {
  const nomes = p.i.map((i) => instPorId[i]).filter(Boolean)
    .map((i) => `<a href="#" data-inst="${esc(i.id)}">${esc(i.sigla || i.nome)}</a>`);
  if (!nomes.length && p.ie) nomes.push(esc(p.ie));
  return nomes.join(", ") + (p.u ? `<br><small>${esc(p.u)}</small>` : "");
}

function links(p) {
  const l = [];
  if (p.l) l.push(`<a href="https://lattes.cnpq.br/${esc(p.l)}" target="_blank" rel="noopener">Lattes</a>`);
  if (p.o) l.push(`<a href="https://orcid.org/${esc(p.o)}" target="_blank" rel="noopener">ORCID</a>`);
  const oa = p.f === "openalex" ? p.id : p.oa;
  if (oa) l.push(`<a href="https://openalex.org/${esc(oa)}" target="_blank" rel="noopener">OpenAlex</a>`);
  return l.join(" · ");
}

function desenharPesquisadores() {
  const lista = ordenar(estado.filtrados);
  const total = lista.length, paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  estado.pagina = Math.min(estado.pagina, paginas - 1);
  const pag = lista.slice(estado.pagina * POR_PAGINA, (estado.pagina + 1) * POR_PAGINA);
  $("n-pesq").textContent = `${fmt(total)} pesquisadores`;
  $("t-pesq").innerHTML = pag.map((p) => `<tr>
    <td>${esc(p.n)}</td><td>${nomeInst(p)}</td>
    <td>${p.t.map((t) => LINHAS[t] ? `<span class="etiqueta" data-linha="${esc(LINHAS[t].nome)}">${esc(LINHAS[t].nome)}</span>` : "").join("")}</td>
    <td class="num">${fmt(p.p)}</td><td class="num">${fmt(p.c)}</td><td class="num">${fmt(p.h)}</td>
    <td>${links(p)}</td></tr>`).join("") || `<tr><td colspan="7">Nenhum pesquisador com esses filtros.</td></tr>`;
  const nav = $("pag-pesq");
  nav.innerHTML = `<button ${estado.pagina === 0 ? "disabled" : ""} data-p="-1">‹ Anterior</button>
    <span>Página ${estado.pagina + 1} de ${paginas}</span>
    <button ${estado.pagina >= paginas - 1 ? "disabled" : ""} data-p="1">Próxima ›</button>`;
  nav.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    estado.pagina += Number(b.dataset.p); desenharPesquisadores(); $("aba-pesquisadores").scrollIntoView();
  }));
}

function desenharInstituicoes() {
  const lista = INST.filter((i) => estado.contagem[i.id]).sort((a, b) => estado.contagem[b.id] - estado.contagem[a.id]);
  $("n-inst").textContent = `${fmt(lista.length)} instituições e laboratórios`;
  $("t-inst").innerHTML = lista.map((i) => `<tr>
    <td><a href="#" data-inst="${esc(i.id)}">${esc(i.nome)}</a>${i.sigla ? ` (${esc(i.sigla)})` : ""}
      ${i.pai && instPorId[i.pai] ? `<br><small>vinculado a ${esc(instPorId[i.pai].nome)}</small>` : ""}</td>
    <td>${esc(i.tipo)}</td><td>${esc(i.cidade || "")}</td>
    <td class="num">${fmt(estado.contagem[i.id])}</td>
    <td>${(i.linhas || []).slice(0, 4).map((t) => LINHAS[t] ? `<span class="etiqueta" data-linha="${esc(LINHAS[t].nome)}">${esc(LINHAS[t].nome)}</span>` : "").join("")}</td>
  </tr>`).join("") || `<tr><td colspan="5">Nenhuma instituição com esses filtros.</td></tr>`;
}

function desenharLinhas() {
  const lista = Object.entries(estado.temas).sort((a, b) => b[1] - a[1]).slice(0, 500);
  $("n-linhas").textContent = `${fmt(Object.keys(estado.temas).length)} linhas de pesquisa` +
    (Object.keys(estado.temas).length > 500 ? " (mostrando as 500 com mais pesquisadores)" : "");
  $("t-linhas").innerHTML = lista.map(([t, n]) => {
    const l = LINHAS[t] || {};
    return `<tr><td><a href="#" data-linha="${esc(l.nome)}">${esc(l.nome)}</a></td>
      <td>${esc(l.area || "")}</td><td>${esc(l.grande_area || "")}</td><td class="num">${fmt(n)}</td></tr>`;
  }).join("");
}

function baixarCsv() {
  const cab = ["nome", "instituicoes", "unidade", "linhas_de_pesquisa", "publicacoes", "citacoes", "indice_h", "orcid", "lattes", "openalex", "fonte"];
  const cel = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const linhas = ordenar(estado.filtrados).map((p) => [
    p.n, p.i.map((i) => instPorId[i]?.nome).filter(Boolean).join("; ") || p.ie, p.u,
    p.t.map((t) => LINHAS[t]?.nome).filter(Boolean).join("; "), p.p, p.c, p.h, p.o, p.l,
    p.f === "openalex" ? p.id : p.oa, p.f,
  ].map(cel).join(","));
  const aviso = cel("Fonte: github.com/Irving-Merath/Lattes - CC BY-NC 4.0 - uso nao comercial, cite o repositorio");
  const blob = new Blob(["﻿" + [aviso, cab.join(","), ...linhas].join("\n")], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "pesquisadores_rj.csv" });
  a.click(); URL.revokeObjectURL(a.href);
}

// Mantém os filtros na URL para que possam ser compartilhados.
const CHAVES_URL = { texto: "f-texto", linha: "f-linha", grande: "f-grande", area: "f-area", cidade: "f-cidade", inst: "f-inst", tipo: "f-tipo", min: "f-min" };
function escreverFiltrosNaUrl() {
  const q = new URLSearchParams();
  for (const [k, id] of Object.entries(CHAVES_URL)) if ($(id).value && $(id).value !== "0") q.set(k, $(id).value);
  if ($("f-lab").checked) q.set("lab", "1");
  history.replaceState(null, "", q.toString() ? `?${q}` : location.pathname);
}
function lerFiltrosDaUrl() {
  const q = new URLSearchParams(location.search);
  for (const [k, id] of Object.entries(CHAVES_URL)) if (q.has(k)) $(id).value = q.get(k);
  $("f-lab").checked = q.get("lab") === "1";
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

carregar().catch((e) => { $("totais").textContent = `Erro ao carregar os dados (${e.message}).`; console.error(e); });
