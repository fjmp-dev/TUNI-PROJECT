#!/bin/bash
# Regenerate the self-signed TLS cert for the suite (LAN only, no public CA).
# SANs cover the mDNS name, localhost and the LAN IP so https works by name or IP.
# Browsers will warn once (self-signed); accept it or import suite.crt as trusted.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout "$DIR/suite.key" -out "$DIR/suite.crt" \
  -subj "/CN=tunisuite.local/O=MIR Suite" \
  -addext "subjectAltName=DNS:tunisuite.local,DNS:localhost,IP:192.168.1.75,IP:127.0.0.1"
chmod 600 "$DIR/suite.key"
echo "[gen_cert] wrote suite.crt / suite.key (valid 825 days)"
