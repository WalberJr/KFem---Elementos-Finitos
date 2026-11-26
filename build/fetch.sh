#!/usr/bin/env bash
# Baixa as fontes de sources.list para $KFEM_DL e confere/registra SHA-256 em sha256.lock.
# 1ª vez: registra o hash (e o relatório da etapa anota a origem). Depois: falha se mudar.
set -euo pipefail
. "$(dirname "$0")/env.sh"
LOCK="$KFEM_ROOT/build/sha256.lock"; touch "$LOCK"
only="${1:-}"
fail=0
while IFS='|' read -r name file url; do
  name=$(echo "$name" | xargs); [[ -z "$name" || "$name" == \#* ]] && continue
  [[ -n "$only" && "$name" != "$only" ]] && continue
  file=$(eval echo "$(echo "$file" | xargs)"); url=$(eval echo "$(echo "$url" | xargs)")
  dest="$KFEM_DL/$file"
  if [[ ! -s "$dest" ]]; then
    echo ">> baixando $name: $url"
    if ! curl -fsSL --retry 3 -o "$dest.part" "$url"; then echo "!! FALHOU $name ($url)"; rm -f "$dest.part"; fail=1; continue; fi
    mv "$dest.part" "$dest"
  fi
  sum=$(sha256sum "$dest" | cut -d' ' -f1)
  old=$(awk -v f="$file" '$2==f{print $1}' "$LOCK")
  if [[ -z "$old" ]]; then echo "$sum  $file" >> "$LOCK"; echo "   registrado $file $sum"
  elif [[ "$old" != "$sum" ]]; then echo "!! SHA-256 DIFERENTE para $file"; fail=1
  else echo "   ok $file"; fi
done < "$KFEM_ROOT/build/sources.list"
exit $fail
