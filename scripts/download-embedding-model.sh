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

REVISION="$(curl -fsSL "$HF_ENDPOINT/api/models/$REPO" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
CACHE_DIR="$DEST/models--${REPO//\//--}"
SNAP_DIR="$CACHE_DIR/snapshots/$REVISION"
mkdir -p "$SNAP_DIR" "$CACHE_DIR/refs"
echo -n "$REVISION" > "$CACHE_DIR/refs/main"

while IFS=$'\t' read -r PATH_IN_REPO EXPECTED_SIZE; do
  OUT="$SNAP_DIR/$PATH_IN_REPO"
  if [ -f "$OUT" ] && [ "$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")" = "$EXPECTED_SIZE" ]; then
    echo "skip $PATH_IN_REPO (already exists)"
    continue
  fi
  mkdir -p "$(dirname "$OUT")"
  echo "downloading $PATH_IN_REPO ..."
  curl -fSL --retry 3 -o "$OUT" "$HF_ENDPOINT/$REPO/resolve/$REVISION/$PATH_IN_REPO"
done < <(curl -fsSL "$HF_ENDPOINT/api/models/$REPO/tree/$REVISION?recursive=true" | python3 -c '
import json, sys
for f in json.load(sys.stdin):
    if f["type"] == "file" and f["path"] not in (".gitattributes", "README.md"):
        print(f["path"], f["size"], sep="\t")')

echo "done. model files are in $SNAP_DIR"
