#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_DIR="$ROOT_DIR/docker/data/nltk"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

BASE_URL="https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"

echo "Downloading NLTK English tokenizer and POS tagger data..."
curl --fail --location --silent --show-error --retry 3 \
  "$BASE_URL/tokenizers/punkt_tab.zip" \
  --output "$TEMP_DIR/punkt_tab.zip"
curl --fail --location --silent --show-error --retry 3 \
  "$BASE_URL/taggers/averaged_perceptron_tagger_eng.zip" \
  --output "$TEMP_DIR/averaged_perceptron_tagger_eng.zip"

mkdir -p "$TEMP_DIR/unpacked" "$DEST_DIR/tokenizers" "$DEST_DIR/taggers"
unzip -q "$TEMP_DIR/punkt_tab.zip" -d "$TEMP_DIR/unpacked"
unzip -q "$TEMP_DIR/averaged_perceptron_tagger_eng.zip" -d "$TEMP_DIR/unpacked"

test -d "$TEMP_DIR/unpacked/punkt_tab/english"
test -d "$TEMP_DIR/unpacked/averaged_perceptron_tagger_eng"
cp -R "$TEMP_DIR/unpacked/punkt_tab" "$DEST_DIR/tokenizers/"
cp -R "$TEMP_DIR/unpacked/averaged_perceptron_tagger_eng" "$DEST_DIR/taggers/"

echo "NLTK data installed under $DEST_DIR"
