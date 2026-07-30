"""roles, items, baskets + colonnes BaseEntity sur users

Revision ID: 2b86203c0955
Revises: f4908d7d2d8d
Create Date: 2026-07-28 22:32:10.832015

Migration générée par `./sqlAlchemy.sh -m "roles items baskets"`, puis AJUSTÉE
À LA MAIN. Alembic écrit lui-même "please adjust!" dans le fichier: son
autogenerate compare les modèles à la base et devine le SQL, mais il ne connaît
rien aux données déjà présentes.

Ici il avait produit:

    batch_op.add_column(sa.Column('email', sa.String(120), nullable=False))

Ça fonctionne sur une base vide et ÉCHOUE sur une base qui contient déjà des
utilisateurs: PostgreSQL doit mettre une valeur dans la nouvelle colonne pour
les lignes existantes, et NOT NULL sans valeur par défaut est impossible.
On ne peut pas non plus mettre server_default='' puisque la colonne est unique.

La bonne recette, en trois temps (à connaître, elle revient tout le temps):
    1. ajouter la colonne en nullable=True
    2. remplir les lignes existantes (UPDATE)
    3. passer la colonne en NOT NULL
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Chaque migration connaît la précédente (down_revision): c'est ce chaînage qui
# permet à Alembic de savoir dans quel ordre appliquer les fichiers.
revision = '2b86203c0955'
down_revision = 'f4908d7d2d8d'
branch_labels = None
depends_on = None


def upgrade():
    # --- nouvelles tables ---------------------------------------------------
    # Ordre imposé par les clés étrangères: items et roles n'en ont pas, donc
    # d'abord; basket_items en dernier (il référence items ET baskets).
    op.create_table('items',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.PrimaryKeyConstraint('item_id')
    )
    # batch_alter_table: mode "recréation de table" nécessaire à SQLite, qui ne
    # sait presque rien modifier avec ALTER TABLE. Inutile sur PostgreSQL, mais
    # inoffensif — et ça rend la migration portable.
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_items_name'), ['name'], unique=True)

    op.create_table('roles',
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('role_name', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.PrimaryKeyConstraint('role_id')
    )
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_roles_role_name'), ['role_name'], unique=True)

    op.create_table('baskets',
    sa.Column('basket_id', sa.Integer(), nullable=False),
    sa.Column('closed', sa.Boolean(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('basket_id')
    )
    # Table d'association user <-> role: clé primaire composée des deux FK.
    op.create_table('user_roles',
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.role_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('role_id', 'user_id')
    )
    op.create_table('basket_items',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('basket_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.ForeignKeyConstraint(['basket_id'], ['baskets.basket_id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.item_id'], ),
    sa.PrimaryKeyConstraint('item_id', 'basket_id')
    )

    # --- 1) email en nullable, le temps de remplir les lignes existantes ----
    op.add_column('users', sa.Column('email', sa.String(length=120), nullable=True))

    # --- 2) backfill --------------------------------------------------------
    # op.execute() envoie du SQL brut: c'est l'outil pour transformer des
    # données dans une migration (Alembic ne le devine jamais tout seul).
    # `||` est la concaténation SQL standard.
    op.execute("""
        UPDATE users
           SET email = username || '@example.local'
         WHERE email IS NULL
    """)

    # --- 3) maintenant la colonne peut devenir obligatoire ------------------
    op.alter_column('users', 'email', nullable=False)

    # Les autres colonnes ont, elles, un server_default: pas besoin de backfill,
    # la base sait quoi mettre dans les lignes déjà là.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=255), server_default='', nullable=False))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
        # La contrainte unique de la migration initiale est remplacée par un
        # index unique (unique=True + index=True sur le modèle). Le nom
        # 'users_username_key' est celui généré automatiquement par PostgreSQL.
        batch_op.drop_constraint(batch_op.f('users_username_key'), type_='unique')
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)


def downgrade():
    # Le downgrade doit défaire l'upgrade, en ordre inverse. Testez-le: c'est
    # votre marche arrière si une migration se passe mal en production.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_unique_constraint(batch_op.f('users_username_key'), ['username'])
        batch_op.drop_column('active')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('description')
        batch_op.drop_column('email')

    op.drop_table('basket_items')
    op.drop_table('user_roles')
    op.drop_table('baskets')
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_roles_role_name'))

    op.drop_table('roles')
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_items_name'))

    op.drop_table('items')
