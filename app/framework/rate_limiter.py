import os
import time
from collections import defaultdict
from functools import wraps
from threading import Lock

from flask import Flask, render_template, request


class RateLimiter:
    """Limiteur de débit par IP, en fenêtre fixe.

    Deux niveaux:

    1. une limite **globale** appliquée à toutes les requêtes (before_request),
       pour absorber un client qui s'emballe;
    2. des limites **par route**, beaucoup plus basses, posées avec le décorateur
       `@rate_limit(...)` sur ce qui coûte cher ou se prête aux abus: connexion,
       inscription, envoi de mail.

    Le compteur est un dictionnaire en mémoire. C'est assumé, et c'est LA limite
    de cette implémentation:

    - il n'est pas partagé entre processus (4 workers gunicorn = 4x la limite);
    - il est perdu au redémarrage;
    - il ne protège pas d'un attaquant distribué sur mille IP.

    En production on met le compteur dans Redis (Flask-Limiter le fait très bien),
    et surtout on limite AUSSI en amont: reverse proxy, WAF (étape suivante),
    CDN. Un limiteur applicatif consomme déjà un processus Python par requête —
    ce qui est exactement ce qu'un attaquant cherche.

    « Fenêtre fixe » plutôt que « fenêtre glissante » ou « token bucket »: le plus
    simple à lire. Son défaut connu: on peut envoyer 2x la limite à cheval sur
    deux fenêtres (voir les exercices).
    """

    def __init__(self, app: Flask):
        self.__app = app
        self.__enabled = os.environ.get("RATE_LIMIT_ENABLED", "True").lower() \
            in ("1", "true", "yes")
        self.__global_max = int(os.environ.get("RATE_LIMIT_GLOBAL_MAX", 240))
        self.__global_window = int(os.environ.get("RATE_LIMIT_GLOBAL_WINDOW", 60))

        # {(clé, fenêtre): compteur}. Le verrou protège contre deux requêtes
        # simultanées qui incrémenteraient la même case (le serveur de dev est
        # multi-thread).
        self.__buckets = defaultdict(int)
        self.__lock = Lock()

        app.rate_limiter = self
        app.before_request(self.__before_request)

    # --- API ----------------------------------------------------------------

    def hit(self, bucket: str, max_requests: int, window: int) -> int:
        """Compte une requête. Retourne les secondes d'attente, 0 si c'est bon."""
        if not self.__enabled:
            return 0

        now = int(time.time())
        # La fenêtre est un numéro de tranche: toutes les requêtes de la même
        # tranche partagent le même compteur, et les anciennes tranches sont
        # simplement abandonnées.
        window_id = now // window
        key = (f"{bucket}:{self.client_ip()}", window_id)

        with self.__lock:
            self.__buckets[key] += 1
            count = self.__buckets[key]

            # Purge opportuniste: sans ça le dictionnaire grandit indéfiniment.
            if len(self.__buckets) > 10_000:
                self.__buckets = defaultdict(
                    int, {k: v for k, v in self.__buckets.items() if k[1] >= window_id})

        if count > max_requests:
            retry_after = (window_id + 1) * window - now
            self.__app.logger.warning(
                f"rate limit: {key[0]} ({count}/{max_requests} en {window}s)")
            return max(1, retry_after)

        return 0

    @staticmethod
    def client_ip() -> str:
        """L'IP du client.

        `request.remote_addr` est l'IP de ce qui parle à Flask: derrière un
        reverse proxy ou un WAF, c'est le proxy, et TOUT LE MONDE partage alors la
        même limite. La vraie IP arrive dans X-Forwarded-For — mais cet en-tête
        est trivialement falsifiable s'il n'est pas posé par un proxy de
        confiance. D'où ProxyFix, ajouté à l'étape « HTTPS et cookies »: il
        remplit remote_addr à partir des en-têtes, en ne faisant confiance qu'au
        nombre de proxys déclaré.
        """
        return request.remote_addr or "inconnu"

    # --- limite globale -----------------------------------------------------

    def __before_request(self):
        # Les fichiers statiques ne passent pas par la limite: une page en charge
        # 10, on épuiserait le quota en trois pages.
        if request.endpoint == 'static':
            return None

        retry_after = self.hit("global", self.__global_max, self.__global_window)

        if retry_after:
            return self.too_many_requests(retry_after)

        return None

    def too_many_requests(self, retry_after: int):
        """La réponse 429, avec l'en-tête que les clients corrects respectent."""
        response = render_template('errors/429.html', retry_after=retry_after)

        return response, 429, {'Retry-After': str(retry_after)}


def rate_limit(max_requests: int, window: int = 60, bucket: str | None = None):
    """Limite une route en particulier.

        @app.route('/login', methods=['GET', 'POST'])
        @rate_limit(10, 60)          # 10 requêtes par minute et par IP
        @inject
        def login(...):

    Placer le décorateur SOUS @app.route (comme @inject): c'est la fonction
    décorée que Flask doit enregistrer.
    """
    def decorateur(func):
        nom = bucket or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Import tardif: le limiteur est créé après les controllers.
            from app import app

            limiter = getattr(app, 'rate_limiter', None)

            if limiter is not None:
                retry_after = limiter.hit(nom, max_requests, window)

                if retry_after:
                    return limiter.too_many_requests(retry_after)

            return func(*args, **kwargs)

        return wrapper

    return decorateur
