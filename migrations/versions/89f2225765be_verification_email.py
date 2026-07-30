"""vérification de l'adresse email à l'inscription

Revision ID: 89f2225765be
Revises: 2b86203c0955
Create Date: 2026-07-29 10:05:09.749499

Migration générée puis AJUSTÉE À LA MAIN (une ligne ajoutée, voir plus bas).

Cette fois l'autogenerate produit du SQL correct: `server_default=false` donne
une valeur aux lignes déjà présentes, la colonne peut donc être NOT NULL tout de
suite. C'est le cas facile, à comparer avec la migration précédente
(`email`, unique et sans valeur par défaut possible).

Mais Alembic ne peut pas décider de la POLITIQUE: faut-il considérer les comptes
existants comme vérifiés, ou les forcer à confirmer leur adresse ?
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '89f2225765be'
down_revision = '2b86203c0955'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(),
                                      server_default=sa.text('false'),
                                      nullable=False))

    # AJOUT MANUEL — la décision fonctionnelle.
    #
    # Les comptes créés avant cette fonctionnalité n'ont jamais eu l'occasion de
    # confirmer leur adresse. Les laisser à `false` les priverait du jour au
    # lendemain de la validation de commande, sans qu'ils y soient pour quoi que
    # ce soit. On les considère donc comme vérifiés: la règle ne s'applique qu'aux
    # inscriptions à partir de maintenant.
    #
    # L'autre politique (tout à `false` + campagne de mails) est défendable pour
    # une application où l'adresse est critique. Ce qui ne l'est pas, c'est de ne
    # pas trancher: sans cette ligne, on choisit « tout le monde bloqué » par
    # défaut, sans l'avoir voulu.
    op.execute("UPDATE users SET email_verified = true")


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_verified')
