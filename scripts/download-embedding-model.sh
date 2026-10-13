#!/usr/bin/env bash
# Pre-download a fastembed local embedding model from HuggingFace into a
# cache directory (default /data/models) that embedding.local.model_path uses.
set -euo pipefail

MODEL="${1:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"
DEST="${2:-/data/models}"
HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"

case "$MODEL" in
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) REPO="Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q" ;;
  BAAI/bge-small-zh-v1.5) REPO="Qdrant/bge-small-zh-v1.5" ;;
  sentence-transformers/all-MiniLM-L6-v2) REPO="Qdrant/all-MiniLM-L6-v2-onnx" ;;
  *) echo "unsupported model: $MODEL" >&2; exit 1 ;;
esac

echo "model : $MODEL"
echo "repo  : $REPO"
echo "dest  : $DEST"

REVISION="$(curl -fsSL "$HF_ENDPOINT/api/models/$REPO" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
echo "rev   : $REVISION"

CACHE_DIR="$DEST/models--${REPO//\//--}"
SNAP_DIR="$CACHE_DIR/snapshots/$REVISION"
mkdir -p "$SNAP_DIR" "$CACHE_DIR/refs"
echo -n "$REVISION" > "$CACHE_DIR/refs/main"

count=0
while IFS='|' read -r PATH_IN_REPO EXPECTED_SIZE; do
  [ -z "$PATH_IN_REPO" ] && continue
  OUT="$SNAP_DIR/$PATH_IN_REPO"
  if [ -f "$OUT" ]; then
    actual_size="$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT" 2>/dev/null || echo 0)"
    if [ "$actual_size" = "$EXPECTED_SIZE" ]; then
      echo "skip   $PATH_IN_REPO ($actual_size bytes, already exists)"
      continue
    else
      echo "resize $PATH_IN_REPO (have $actual_size, want $EXPECTED_SIZE)"
    fi
  fi
  mkdir -p "$(dirname "$OUT")"
  echo "get    $PATH_IN_REPO ($EXPECTED_SIZE bytes)"
  curl -fSL --retry 3 -o "$OUT" "$HF_ENDPOINT/$REPO/resolve/$REVISION/$PATH_IN_REPO"
  count=$((count + 1))
done < <(curl -fsSL "$HF_ENDPOINT/api/models/$REPO/tree/$REVISION?recursive=true" | python3 -c '
import json, sys
for f in json.load(sys.stdin):
    if f["type"] == "file" and f["path"] not in (".gitattributes", "README.md"):
        print(f["path"], f["size"], sep="|")')

echo "done. $count file(s) downloaded; model files in $SNAP_DIR"
