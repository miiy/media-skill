#!/usr/bin/env bash
# Convert docx files to PDF with LibreOffice.
# Usage: bash docx2pdf.sh <docx-dir|file.docx...> [-o <out-dir>] [--overwrite]
# Existing PDFs are skipped unless --overwrite is given.
set -u
OUT="."
OVERWRITE=0
INPUTS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -o|--out) OUT="$2"; shift 2 ;;
    -f|--overwrite) OVERWRITE=1; shift ;;
    -h|--help)
      echo "Usage: bash docx2pdf.sh <docx-dir|file.docx...> [-o <out-dir>] [--overwrite]"
      exit 0 ;;
    *) INPUTS+=("$1"); shift ;;
  esac
done

SOFFICE="$(command -v soffice || echo /Applications/LibreOffice.app/Contents/MacOS/soffice)"
if [ ! -x "$SOFFICE" ]; then
  echo "LibreOffice not found. Two options:"
  echo "  1) Open each docx in Word and use Save As > PDF (no dependencies, best fidelity, recommended for one-off cases)"
  echo "  2) Install LibreOffice and rerun: brew install --cask libreoffice"
  exit 1
fi

FILES=()
for f in "${INPUTS[@]}"; do
  if [ -d "$f" ]; then
    while IFS= read -r x; do FILES+=("$x"); done < <(find "$f" -maxdepth 1 -name '*.docx' ! -name '~$*' | sort)
  elif [ -f "$f" ]; then
    FILES+=("$f")
  else
    echo "! not found: $f" >&2
  fi
done
if [ ${#FILES[@]} -eq 0 ]; then
  echo "No .docx input found." >&2
  exit 1
fi

mkdir -p "$OUT"
# Use a throwaway user profile: the default one fails with DeploymentException when it is
# locked, read-only, or another LibreOffice instance is already running.
PROFILE="$(mktemp -d "${TMPDIR:-/tmp}/docx2pdf.XXXXXX" 2>/dev/null || echo "/tmp/docx2pdf.$$")"
trap 'rm -rf "$PROFILE"' EXIT

converted=0; skipped=0; failed=0
for f in "${FILES[@]}"; do
  base="$(basename "${f%.*}")"
  target="$OUT/$base.pdf"
  if [ -f "$target" ] && [ "$OVERWRITE" -eq 0 ]; then
    echo "- skipped (exists): $target"
    skipped=$((skipped + 1))
    continue
  fi
  rm -f "$target"
  "$SOFFICE" -env:UserInstallation="file://$PROFILE" --headless --convert-to pdf --outdir "$OUT" "$f" >/dev/null 2>&1
  if [ -s "$target" ]; then
    echo "✓ $target ($(du -h "$target" | cut -f1 | tr -d ' '))"
    converted=$((converted + 1))
  else
    echo "! failed: $f" >&2
    failed=$((failed + 1))
  fi
done

echo "converted $converted, skipped $skipped, failed $failed"
[ "$failed" -eq 0 ]
