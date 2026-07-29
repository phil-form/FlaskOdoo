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

from app import app

port = int(os.environ.get('PORT', 8080))

app.run('0.0.0.0', port=port)
