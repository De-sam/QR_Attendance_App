"""Add google_id column to User model

Revision ID: 0191ac81bb98
Revises: 95d08fa02276
Create Date: 2024-05-27 13:08:06.612943

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0191ac81bb98'
down_revision = '95d08fa02276'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the deadline column
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_column('deadline')

    # Recreate the deadline column with the NOT NULL constraint and a default value
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deadline', sa.DateTime(), nullable=False, server_default='2024-12-31'))

    # Update existing records with a default value for the deadline
    op.execute("UPDATE locations SET deadline = '2024-12-31' WHERE deadline IS NULL")

    # Add the google_id column to the users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_id', sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint(None, ['google_id'])

def downgrade():
    # Drop the google_id column from the users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_column('google_id')

    # Drop the deadline column from the locations table
    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_column('deadline')