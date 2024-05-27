"""Add google_id column to User model

Revision ID: 0efcf529f836
Revises: 0191ac81bb98
Create Date: 2024-05-27 14:27:22.254064

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0efcf529f836'
down_revision = '0191ac81bb98'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.alter_column('deadline',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.Time(),
               existing_nullable=False,
               existing_server_default=sa.text("'2024-12-31 00:00:00'::timestamp without time zone"))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('profile_image_url', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('profile_image_url')

    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.alter_column('deadline',
               existing_type=sa.Time(),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False,
               existing_server_default=sa.text("'2024-12-31 00:00:00'::timestamp without time zone"))

    # ### end Alembic commands ###