import inspect
from functools import wraps

from app import app


def inject(func):
    """Injecte les dépendances annotées de la fonction décorée.

        @app.get('/items')
        @inject
        def item_list(item_service: ItemService):
            ...

    Le décorateur lit les annotations de type (`item_service: ItemService`),
    demande chaque type à l'injecteur, et passe les instances en kwargs.
    Flask, lui, ne voit qu'une fonction sans paramètre: il n'essaiera donc pas
    de remplir item_service depuis l'URL.

    Attention à l'ordre des décorateurs: @app.route doit être AU-DESSUS de
    @inject, sinon Flask enregistre la fonction non décorée.
    """

    @wraps(func)
    def function_wrapper(*args, **kwargs):
        arguments = inspect.getfullargspec(func)

        for key, val in arguments.annotations.items():
            # 'return' est aussi une annotation, mais ce n'est pas un paramètre.
            if key == 'return':
                continue

            # Ne pas écraser ce que Flask a déjà fourni (ex: <int:user_id>).
            if key in kwargs:
                continue

            to_inject = app.injector[val.__name__]

            if to_inject is not None:
                kwargs[key] = to_inject

        return func(*args, **kwargs)

    return function_wrapper
