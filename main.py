"""Lanceur du serveur de développement.

    $ python main.py

Tout le câblage est fait dans app/__init__.py: ici on ne fait que démarrer le
serveur. Pour déboguer depuis PyCharm ou VSCode, c'est ce fichier qu'il faut
pointer comme programme à lancer.

'0.0.0.0' = écouter sur toutes les interfaces réseau (et pas seulement
127.0.0.1), indispensable quand l'app tourne dans un conteneur Docker: sinon
le port publié ne reçoit rien.

Ce serveur est mono-processus et non optimisé: c'est un outil de
développement. En production on passe par un serveur WSGI (gunicorn, uwsgi)
avec DEBUG=False.
"""
import os
from pathlib import Path

from app import app

port = int(os.environ.get('PORT', 8080))

# --- HTTPS en développement -------------------------------------------------
# HTTPS=True dans le .env.local pour servir en https://localhost:8080.
#
# Trois façons de faire, par ordre de réalisme:
#
# 1. `ssl_context='adhoc'`: Werkzeug fabrique un certificat jetable à chaque
#    démarrage (paquet `cryptography`). Le navigateur hurle, on clique
#    « continuer ». Parfait pour vérifier qu'un cookie Secure part bien.
# 2. un certificat auto-signé persistant (voir certs/generer.sh): le navigateur
#    hurle une seule fois si on l'ajoute aux exceptions.
# 3. en production: on ne fait PAS le TLS ici. Un reverse proxy (nginx, le WAF de
#    l'étape suivante, un load balancer) le termine et parle en HTTP clair à
#    l'application — d'où ProxyFix dans app/__init__.py.
ssl_context = None

if os.environ.get("HTTPS", "False").lower() in ("1", "true", "yes"):
    cert = Path("certs/localhost.pem")
    key = Path("certs/localhost-key.pem")

    ssl_context = (str(cert), str(key)) if cert.exists() and key.exists() else 'adhoc'

app.run('0.0.0.0', port=port, ssl_context=ssl_context)
