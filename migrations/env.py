from alembic import context
from sqlalchemy import create_engine

from lotto_model.config import Settings

url = context.config.attributes.get("database_url")
if url is None:
    url = Settings().database_url.get_secret_value()

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
