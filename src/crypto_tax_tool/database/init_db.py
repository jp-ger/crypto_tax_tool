from crypto_tax_tool.database.connection import Base, get_engine


def initialize_database() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
