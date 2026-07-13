#!/bin/bash
# Install the suite's root CA (ca.crt) into every certificate store on THIS machine,
# so browsers stop showing "Your connection is not private" / ERR_CERT_AUTHORITY_INVALID.
#
# Why a script: Firefox and Chrome do NOT use the system trust store on Linux -- each
# keeps its own NSS database, and the snap packages keep theirs in a private path
# (~/snap/<app>/current/.pki/nssdb) that the non-snap path does not touch. Installing
# into the "obvious" store silently fixes nothing, which is exactly the trap this
# script exists to avoid.
#
# No sudo needed for the browser stores (they are per-user). The system store
# (/usr/local/share/ca-certificates) is only attempted if sudo is available -- that
# one covers curl/python/wget, not browsers.
#
# Restart the browser completely afterwards: NSS is read at startup.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
CA="$DIR/ca.crt"
NAME="MIR Suite Local CA"

[ -f "$CA" ] || { echo "no $CA -- run gen_cert.sh first"; exit 1; }

# certutil (libnss3-tools) is what writes an NSS db. If it is not installed, fetch the
# package and unpack it locally instead of demanding sudo for a one-shot tool.
CERTUTIL="$(command -v certutil || true)"
if [ -z "$CERTUTIL" ]; then
  TMP="$(mktemp -d)"
  echo "[trust_ca] certutil not installed; unpacking libnss3-tools into $TMP"
  ( cd "$TMP" && apt-get download libnss3-tools >/dev/null 2>&1 && dpkg-deb -x libnss3-tools_*.deb . )
  CERTUTIL="$TMP/usr/bin/certutil"
  [ -x "$CERTUTIL" ] || { echo "could not obtain certutil; install libnss3-tools"; exit 1; }
fi

# Every NSS store that could exist for this user. Globs cover snap's versioned dirs
# and each Firefox profile (a profile that has never been launched has no db yet).
STORES=(
  "$HOME/.pki/nssdb"                          # Chrome/Chromium (deb)
  "$HOME/snap/chromium/current/.pki/nssdb"    # Chromium (snap)  <-- the one that bit us
  "$HOME"/.mozilla/firefox/*.default*         # Firefox (deb)
  "$HOME"/snap/firefox/common/.mozilla/firefox/*.default*  # Firefox (snap)
)

found=0
for db in "${STORES[@]}"; do
  [ -d "$db" ] || continue
  [ -f "$db/cert9.db" ] || "$CERTUTIL" -d "sql:$db" -N --empty-password >/dev/null 2>&1 || continue
  # -A is idempotent for a given nickname: re-running replaces, never duplicates.
  if "$CERTUTIL" -d "sql:$db" -A -t "C,," -n "$NAME" -i "$CA" 2>/dev/null; then
    echo "[trust_ca] OK  $db"
    found=$((found + 1))
  else
    echo "[trust_ca] FAILED  $db"
  fi
done
[ "$found" -gt 0 ] || echo "[trust_ca] no browser NSS stores found for user $USER"

# System store: curl/python/wget only. Browsers ignore it.
if sudo -n true 2>/dev/null; then
  sudo cp "$CA" /usr/local/share/ca-certificates/mir-suite-ca.crt
  sudo update-ca-certificates >/dev/null
  echo "[trust_ca] OK  system store (curl/python)"
else
  echo "[trust_ca] skipped system store (needs sudo):"
  echo "           sudo cp $CA /usr/local/share/ca-certificates/mir-suite-ca.crt && sudo update-ca-certificates"
fi

echo
echo "[trust_ca] done -- now QUIT the browser completely (all windows) and reopen it."
echo "[trust_ca] then browse https://mir-suite.local  (or https://192.168.1.75)"
