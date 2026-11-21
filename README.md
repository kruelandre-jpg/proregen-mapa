# Proregen — Rede Nacional (mapa 3D)

Cópia estática do mapa 3D da rede Proregen, hospedada no GitHub Pages:
https://kruelandre-jpg.github.io/proregen-mapa/

Origem: build publicado pelo Manus em https://proregen3d-eqfgf7qq.manus.space (versão de6cf715, 21/11/2026).
O código-fonte React/Vite fica no Manus; aqui está o build já compilado.

## Pastas

- `upstream/` build baixado do Manus, sem alteração (referência)
- `docs/` o que o GitHub Pages publica (gerado pelo script, não editar à mão)
- `data/clinicas.json` lista usada no mapa quando o build roda com `--dados oficial`
- `scripts/mirror.sh` baixa de novo o build do Manus para `upstream/`
- `scripts/build.py` gera `docs/` (caminhos relativos, base `/proregen-mapa`, sem analytics do Manus, descrição com a contagem certa)

## Atualizar a lista de clínicas

1. Atualize a lista oficial em `/workspace/clinicas/` (ver `COMO-ATUALIZAR.md` lá).
2. `python3 scripts/build.py --dados oficial --so-diff` mostra o que muda no mapa.
3. `python3 scripts/build.py --dados oficial` reescreve o array de clínicas dentro do bundle minificado.
4. Commit e push na `main`. O Pages atualiza em cerca de um minuto.

A lista oficial é a única fonte: um ponto no mapa por local (Tubarão gera 2 pinos). Clínica de um só local reaproveita a coordenada municipal do mapa antigo, se houver; locais extras usam a geocodificação oficial. A categoria (Ortopedia ou Unique) vem da lista oficial (Regular vira Ortopedia).
