from uuid import uuid4

from sqlalchemy import String


UUID_LENGTH = 36
UUID_SQL_TYPE = String(UUID_LENGTH)


def new_uuid() -> str:
    return str(uuid4())
