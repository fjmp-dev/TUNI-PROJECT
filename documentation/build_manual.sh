#!/bin/bash
# Regenerate MIR_SUITE_MANUAL.docx from MIR_SUITE_MANUAL.md.
#
# The Markdown is the master (diffable, reviewed in git); the .docx is a build
# artifact. Rebuild it whenever the manual changes -- a Word file edited by hand
# will rot exactly like the documents this manual replaced.
#
# Conversion: pandoc, via the pypandoc-binary wheel (`pip3 install --user
# pypandoc-binary`) because there is no pandoc apt package installed on the Jetson.
# Fallback if pandoc is unavailable: python-markdown -> HTML -> LibreOffice
# (`soffice --headless --convert-to docx`), which this Jetson does have.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
MD="$DIR/MIR_SUITE_MANUAL.md"
OUT="$DIR/MIR_SUITE_MANUAL.docx"

if python3 -c "import pypandoc" 2>/dev/null; then
  # --resource-path so the manual_images/ screenshots embed; --toc for a real
  # Word table of contents.
  python3 - "$MD" "$OUT" <<'PY'
import sys, pypandoc
md, out = sys.argv[1], sys.argv[2]
pypandoc.convert_file(
    md, "docx", outputfile=out,
    extra_args=["--toc", "--toc-depth=2", f"--resource-path={md.rsplit('/',1)[0]}",
                "--metadata", "title=MIR Suite - Technical Manual"])
print(f"[build_manual] pandoc -> {out}")
PY
else
  echo "[build_manual] pypandoc missing; falling back to markdown -> HTML -> LibreOffice"
  python3 - "$MD" "$DIR/.manual_tmp.html" <<'PY'
import sys, markdown, pathlib
md, out = sys.argv[1], sys.argv[2]
body = markdown.markdown(pathlib.Path(md).read_text(), extensions=["tables", "fenced_code"])
style = "body{font-family:Calibri,sans-serif;max-width:19cm} table{border-collapse:collapse} td,th{border:1px solid #999;padding:4px 8px} code,pre{font-family:Consolas,monospace;background:#f4f4f4} img{max-width:100%}"
pathlib.Path(out).write_text(f"<html><head><meta charset='utf-8'><style>{style}</style></head><body>{body}</body></html>")
PY
  (cd "$DIR" && soffice --headless --convert-to docx --outdir "$DIR" .manual_tmp.html >/dev/null \
    && mv .manual_tmp.docx "$OUT" && rm -f .manual_tmp.html)
  echo "[build_manual] soffice -> $OUT"
fi
ls -lh "$OUT"
