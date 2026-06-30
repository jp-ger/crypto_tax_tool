from crypto_tax_tool.database.sqlite_store import initialize_sqlite


def initialize_database() -> None:
    initialize_sqlite()
