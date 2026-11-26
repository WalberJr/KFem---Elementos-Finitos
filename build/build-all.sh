#!/usr/bin/env bash
# Executa as receitas em ordem; cada uma tem log próprio em $KFEM_LOGS. Uso: build-all.sh [primeira] [última]
set -uo pipefail
. "$(dirname "$0")/env.sh"
first="${1:-00}"; last="${2:-99}"
for r in "$KFEM_ROOT"/build/recipes/[0-9][0-9]-*.sh; do
  n=$(basename "$r" .sh); num=${n%%-*}
  [[ "$num" < "$first" || "$num" > "$last" ]] && continue
  echo "[$(date +%H:%M:%S)] >> $n"
  if ! bash "$r" > "$KFEM_LOGS/$n.log" 2>&1; then
    echo "[$(date +%H:%M:%S)] !! $n FALHOU — ver $KFEM_LOGS/$n.log"; tail -25 "$KFEM_LOGS/$n.log"; exit 1
  fi
  echo "[$(date +%H:%M:%S)]    $n ok"
done
echo "[$(date +%H:%M:%S)] concluído"
