"""Add timezone to User model and remove UserTimeZone table

Revision ID: 95d08fa02276
Revises: 571396e7fa53
Create Date: 2024-05-16 20:51:34.581471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95d08fa02276'
down_revision = '571396e7fa53'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the usertimezones table
    op.drop_table('usertimezones')
    
    # Add the timezone column with a default value
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(length=50), nullable=True))
    
    # Update existing rows to set the default timezone
    op.execute('UPDATE users SET timezone = \'UTC\' WHERE timezone IS NULL')
    
    # Alter the column to make it NOT NULL
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('timezone', nullable=False)


def downgrade():
    # Drop the timezone column
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('timezone')
    
    # Recreate the usertimezones table
    op.create_table('usertimezones',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('time_zone', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='usertimezones_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='usertimezones_pkey')
    )
    