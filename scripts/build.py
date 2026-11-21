#!/usr/bin/env python3
"""Gera docs/ (site do GitHub Pages) a partir do build espelhado do Manus em upstream/.

Uso:
  python3 scripts/build.py                     # espelho fiel (dados do Manus)
  python3 scripts/build.py --dados oficial     # troca a lista pela lista oficial
  python3 scripts/build.py --dados oficial --so-diff   # só mostra o que mudaria

O que o build faz:
  * caminhos absolutos (/assets, /manus-storage) viram relativos, para rodar em /proregen-mapa/
  * define a base do roteador (wouter) para /proregen-mapa
  * remove analytics do Manus (umami, plausible) e o manifest PWA do Manus
  * corrige og:url, canonical, og:image e a descrição (contagem tirada dos dados)
  * com --dados oficial, reescreve o array de clínicas do bundle a partir de
    /workspace/clinicas/unidades.publico.json + medicos.json e grava data/clinicas.json
"""
from __future__ import annotations
import argparse, json, re, shutil, sys, unicodedata, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UP, OUT = ROOT / "upstream", ROOT / "docs"
REGIAO = {**dict.fromkeys("RS SC PR".split(), "Sul"), **dict.fromkeys("SP RJ MG ES".split(), "Sudeste"),
          **dict.fromkeys("MA PI CE RN PB PE AL SE BA".split(), "Nordeste"),
          **dict.fromkeys("AC AP AM PA RO RR TO".split(), "Norte"), **dict.fromkeys("DF GO MT MS".split(), "Centro-Oeste")}

def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def chave(s: str) -> str:
    s = re.sub(r"^(Dr|Dra)\.\s+", "", s)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def acha_array(js: str):
    m = re.search(r"([A-Za-z_$][\w$]*)=\[\{id:\"[a-z0-9-]+\",city:", js)
    if not m:
        sys.exit("array de clínicas não encontrado no bundle")
    i = m.start() + len(m.group(1)) + 1
    depth, j, q = 0, i, None
    while True:
        c = js[j]
        if q:
            if c == "\\": j += 2; continue
            if c == q: q = None
        elif c in "\"'`": q = c
        elif c in "[{(": depth += 1
        elif c in "]})":
            depth -= 1
            if depth == 0: break
        j += 1
    return m.group(1), i, j + 1

def avalia(literal: str):
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False) as f:
        f.write("process.stdout.write(JSON.stringify(" + literal + "))")
    return json.loads(subprocess.check_output(["node", f.name]))

def lista_oficial(pasta: Path, atual: list[dict]) -> list[dict]:
    U = json.loads((pasta / "unidades.publico.json").read_text())["unidades"]
    M = json.loads((pasta / "medicos.json").read_text())["medicos"]
    velho = {c["id"]: c for c in atual}
    por_num: dict[int, list] = {}
    for u in U:
        por_num.setdefault(u["numero"], []).append(u)
    out = []
    for num, locais in por_num.items():
        locais.sort(key=lambda x: x.get("local") or 1)
        u = locais[0]
        cid = slug(f'{u["cidade"]}-{u["uf"]}')
        v = velho.get(cid, {})
        meds = sorted([m for m in M if m["numero_unidade"] == num], key=lambda m: chave(m["nome"]))
        c = {"id": cid, "city": u["cidade"], "state": u["uf"],
             "lat": v.get("lat", round(u["lat"], 4)), "lng": v.get("lng", round(u["lon"], 4)),
             "region": REGIAO[u["uf"]],
             "category": "Matriz" if u["e_matriz"] else v.get("category", "Ortopedia"),
             "unitName": re.sub(r"\s*\(local \d+:.*\)$", "", u["nome"]),
             "members": [{"name": m["nome"], "registration": m["crm_rqe"], "specialty": m["especialidade"]} for m in meds]}
        if v.get("members") and {m["name"] for m in v["members"]} == {m["name"] for m in c["members"]}:
            ordem = [m["name"] for m in v["members"]]
            c["members"].sort(key=lambda m: ordem.index(m["name"]))
        c["doctorCount"] = len(c["members"])
        c["doctors"] = (f'{len(c["members"])} profissionais na equipe informada' if len(c["members"]) >= 5
                        else " · ".join(m["name"] for m in c["members"]))
        c["phones"] = u.get("telefones") or []
        c["instagram"] = [i.lstrip("@") for i in (u.get("instagram") or [])]
        if u.get("endereco"):
            c["address"] = u["endereco"]
            if u.get("bairro"): c["neighborhood"] = u["bairro"]
            if u.get("cep"): c["postalCode"] = u["cep"]
        else:
            c["addressPending"] = True
            if v.get("note"): c["note"] = v["note"]
        extra = [f'{l["endereco"]}, {l["bairro"]}' if l.get("bairro") else l["endereco"] for l in locais[1:] if l.get("endereco")]
        if extra:
            c["note"] = "Também atende em: " + "; ".join(extra) + "."
        sites = [s for s in (u.get("sites") or []) if s.startswith("http")]
        if sites: c["website"] = "\n".join(sites)
        if u["e_matriz"]: c["headquarters"] = True
        out.append(c)
    out.sort(key=lambda c: (0 if c.get("headquarters") else 1, c["id"]))
    return out

def diff(a: list[dict], b: list[dict]):
    A, B = {c["id"]: c for c in a}, {c["id"]: c for c in b}
    for k in sorted(A.keys() - B.keys()): print(f"- sai: {k}")
    for k in sorted(B.keys() - A.keys()): print(f"+ entra: {k}")
    for k in sorted(A.keys() & B.keys()):
        for f in sorted(set(A[k]) | set(B[k])):
            if A[k].get(f) != B[k].get(f):
                print(f"~ {k}.{f}: {json.dumps(A[k].get(f), ensure_ascii=False)[:140]} -> {json.dumps(B[k].get(f), ensure_ascii=False)[:140]}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/proregen-mapa")
    ap.add_argument("--url", default="https://kruelandre-jpg.github.io/proregen-mapa/")
    ap.add_argument("--dados", choices=["manus", "oficial"], default="manus")
    ap.add_argument("--pasta-oficial", default="/workspace/clinicas")
    ap.add_argument("--so-diff", action="store_true")
    a = ap.parse_args()

    html = (UP / "index.html").read_text()
    main_js = re.search(r'src="/assets/([^"]+\.js)"', html).group(1)
    js = (UP / "assets" / main_js).read_text()
    nome, i, j = acha_array(js)
    atual = avalia(js[i:j])
    clinicas = atual
    if a.dados == "oficial":
        clinicas = lista_oficial(Path(a.pasta_oficial), atual)
        print(f"diferenças Manus -> oficial ({len(atual)} -> {len(clinicas)} pontos):"); diff(atual, clinicas)
        if a.so_diff: return
        js = js[:i] + json.dumps(clinicas, ensure_ascii=False, separators=(",", ":")) + js[j:]
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "clinicas.json").write_text(json.dumps(clinicas, ensure_ascii=False, indent=1) + "\n")
        from datetime import date
        d = json.loads((Path(a.pasta_oficial) / "unidades.publico.json").read_text())["meta"]["atualizado_em"]
        y, m, dd = d.split("-")
        js = re.sub(r'(const [\w$]+=)"\d\d/\d\d/\d{4}"(,' + re.escape(nome) + r'=\[)', rf'\g<1>"{dd}/{m}/{y}"\2', js, count=1)

    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(UP, OUT)
    # roteador: base do wouter
    js, n = re.subn(r'(searchHook:[\w$]+,parser:[\w$]+,)base:""', rf'\1base:"{a.base}"', js, count=1)
    if n != 1: sys.exit("não achei a base do roteador wouter")
    js = js.replace('"/manus-storage/', '"./manus-storage/')
    (OUT / "assets" / main_js).write_text(js)
    for f in (OUT / "assets").glob("*.js"):
        if f.name != main_js:
            t = f.read_text().replace('"/manus-storage/', '"./manus-storage/')
            f.write_text(t)

    ufs = {c["state"] for c in clinicas}
    afil = len([c for c in clinicas if not c.get("headquarters")])
    est = len(ufs - {"DF"})
    desc = f"Mapa 3D interativo da rede nacional Proregen: a matriz e {afil} clínicas afiliadas em {est} estados" + (" e o DF." if "DF" in ufs else ".")
    html = html.replace('src="/assets/', 'src="./assets/').replace('href="/assets/', 'href="./assets/').replace('href="/manus-storage/', 'href="./manus-storage/')
    html = re.sub(r'(name="description"\s+content=")[^"]*"', rf'\g<1>{desc}"', html)
    html = re.sub(r'(property="og:description" content=")[^"]*"', rf'\g<1>{desc}"', html)
    html = re.sub(r'(name="twitter:description" content=")[^"]*"', rf'\g<1>{desc}"', html)
    html = re.sub(r'https://[a-z0-9-]+\.manus\.space/__manus/checkpoint-screenshot\.png[^"]*', a.url + "og.png", html)
    html = re.sub(r'https://[a-z0-9-]+\.manus\.space/', a.url, html)
    html = re.sub(r'<link rel="manifest"[^>]*/>', "", html)
    html = re.sub(r'\s*<script\s+defer\s+src="https://manus-analytics\.com/umami"[^>]*></script>', "", html)
    html = re.sub(r'\s*<script\s+defer\s+data-domain="manus\.space"[\s\S]*?</script>\s*<script>[\s\S]*?</script>', "", html)
    if "manus" in re.sub(r"manus-storage", "", html):
        print("aviso: ainda há referência a manus no index.html")
    (OUT / "index.html").write_text(html)
    (OUT / "404.html").write_text(html)
    (OUT / ".nojekyll").write_text("")
    print(f"docs/ gerado: {len(clinicas)} pontos ({afil} afiliadas + matriz), {est} estados{' + DF' if 'DF' in ufs else ''}; dados={a.dados}")

if __name__ == "__main__":
    main()
