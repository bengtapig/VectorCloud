"""empty message

Revision ID: c35ca321cd21
Revises: e15b6cdfad5c
Create Date: 2018-12-31 19:11:08.607454

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c35ca321cd21'
down_revision = 'e15b6cdfad5c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('view')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('view', sa.TEXT(), nullable=True))

    # ### end Alembic commands ###
