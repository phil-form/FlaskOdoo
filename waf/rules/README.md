# Règles personnalisées

Ce dossier est monté dans le conteneur du WAF. On y met les règles **propres à
l'application**, celles qu'un jeu de règles générique ne peut pas connaître.

Exemple: bloquer les requêtes vers `/admin.php`, `/wp-login.php` et compagnie.
Elles n'existent pas chez nous, donc toute requête vers ces chemins est un
scanner. Les arrêter au WAF évite de journaliser des centaines de 404 par jour.

```
SecRule REQUEST_URI "@rx (?i)/(wp-login|wp-admin|admin\.php|phpmyadmin)" \
    "id:2000,phase:1,deny,status:403,log,msg:'Scanner connu'"
```

Attention: chaque `id:` doit être unique. Les plages 1-99999 sont réservées à
l'usage local, le CRS utilise 900000-999999.
