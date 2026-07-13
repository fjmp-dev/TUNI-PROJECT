#!/bin/bash
# Regenerate the suite's TLS material (LAN only, no public CA).
#
# Two tiers on purpose:
#   ca.crt / ca.key   -- our own root CA ("MIR Suite Local CA"), valid 10 years.
#                        Install ca.crt ONCE as a trusted authority on each device
#                        that browses the suite -> no more "dangerous site" warning.
#   suite.crt / .key  -- the server cert Caddy serves, signed by that CA, 825 days.
#
# The root is what devices trust, so the server cert can be reissued (new IP, new
# name, expiry) WITHOUT reinstalling anything on the laptops/phones -- that is the
# whole point of not using a single self-signed cert like the first version did.
#
# ca.key never leaves this machine (chmod 600, gitignored by *.key). ca.crt is
# public: Caddy serves it at https://<host>/ca.crt so phones can install it.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# Names/addresses a browser may use to reach the suite. tunisuite.local stays for
# old bookmarks; mir-suite.local is the mDNS alias published by the mir_mdns
# container; lab.local is the Jetson's own hostname (avahi already publishes it).
SANS="DNS:mir-suite.local,DNS:tunisuite.local,DNS:lab.local,DNS:localhost,IP:192.168.1.75,IP:127.0.0.1"

# --- Root CA (created once; reused on later runs so trust stores stay valid) ---
if [ ! -f "$DIR/ca.key" ] || [ ! -f "$DIR/ca.crt" ]; then
  openssl req -x509 -newkey rsa:4096 -nodes -days 3650 -sha256 \
    -keyout "$DIR/ca.key" -out "$DIR/ca.crt" \
    -subj "/CN=MIR Suite Local CA/O=MIR Suite" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
  chmod 600 "$DIR/ca.key"
  echo "[gen_cert] created NEW root CA (ca.crt) -- must be installed on every browser"
else
  echo "[gen_cert] reusing existing root CA (devices keep trusting it)"
fi

# --- Server certificate, signed by the CA ---
openssl req -newkey rsa:2048 -nodes -sha256 \
  -keyout "$DIR/suite.key" -out "$DIR/suite.csr" \
  -subj "/CN=mir-suite.local/O=MIR Suite"

openssl x509 -req -in "$DIR/suite.csr" -days 825 -sha256 \
  -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial \
  -out "$DIR/suite.crt" \
  -extfile <(printf "subjectAltName=%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$SANS")

rm -f "$DIR/suite.csr"
chmod 600 "$DIR/suite.key"
chmod 644 "$DIR/suite.crt" "$DIR/ca.crt"

echo "[gen_cert] wrote suite.crt (825 days), signed by ca.crt"
echo "[gen_cert] SANs: $SANS"
echo "[gen_cert] restart Caddy to pick it up:  docker restart mir_caddy"
