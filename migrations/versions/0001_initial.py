"""Create application schema."""
from alembic import op
from app.models import Base
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
    if op.get_bind().dialect.name=="postgresql":
        op.execute("CREATE INDEX IF NOT EXISTS ix_articles_search ON articles USING GIN (to_tsvector('simple', title || ' ' || content))")
def downgrade():
    if op.get_bind().dialect.name=="postgresql":op.execute("DROP INDEX IF EXISTS ix_articles_search")
    Base.metadata.drop_all(bind=op.get_bind())
