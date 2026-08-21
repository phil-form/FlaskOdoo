#!/usr/bin/env bash
# Génère un certificat auto-signé pour le développement local.
#
#   ./certs/generer.sh && HTTPS=True python main.py
#
# Auto-signé = aucune autorité ne le garantit: le navigateur affiche un
# avertissement. C'est normal et suffisant en local. En production, un
# certificat gratuit Let's Encrypt (certbot) est délivré par une autorité
# reconnue, et se renouvelle tout seul.
set -euo pipefail
cd "$(dirname "$0")"

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout localhost-key.pem -out localhost.pem \
    -days 365 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "certificat généré: certs/localhost.pem (valable 365 jours)"
