#!/usr/bin/env bash
# Baixa de novo o build publicado no Manus para upstream/ (somente leitura do site público).
set -euo pipefail
SRC="${SRC:-https://proregen3d-eqfgf7qq.manus.space}"
cd "$(dirname "$0")/.."
rm -rf upstream.new && mkdir -p upstream.new/assets upstream.new/manus-storage
curl -fsSL "$SRC/" -o upstream.new/index.html
for a in $(grep -oE '/assets/[A-Za-z0-9._-]+\.(js|css)' upstream.new/index.html | sort -u); do curl -fsSL "$SRC$a" -o "upstream.new$a"; done
# chunks importados dinamicamente
for js in upstream.new/assets/*.js; do
  for c in $(grep -oE 'import\("\./[A-Za-z0-9._-]+\.js"\)' "$js" | grep -oE '[A-Za-z0-9._-]+\.js' | sort -u); do
    [ -f "upstream.new/assets/$c" ] || curl -fsSL "$SRC/assets/$c" -o "upstream.new/assets/$c"; done; done
for f in $(cat upstream.new/index.html upstream.new/assets/*.js | grep -oE '/manus-storage/[A-Za-z0-9._-]+' | sort -u); do curl -fsSL "$SRC$f" -o "upstream.new$f"; done
v=$(grep -oE 'checkpoint-screenshot\.png\?v=[a-z0-9]+' upstream.new/index.html | head -1 | cut -d= -f2)
curl -fsSL "$SRC/__manus/checkpoint-screenshot.png?v=$v&badge=0" -o upstream.new/og.png || true
rm -rf upstream && mv upstream.new upstream
echo "upstream atualizado de $SRC (versão $v)"
