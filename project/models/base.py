import datetime

from sqlalchemy import Column, types
from sqlalchemy.ext.declarative import declarative_base, declared_attr

from project.utils import *


class DefaultBase(object):
    @declared_attr
    def __tablename__(cls):
        return camel_to_snake(cls.__name__)

    def __repr__(self):
        try:
            return f'{type(self).__name__} id={getattr(self, "id")}'
        except AttributeError:
            return f'{type(self).__name__}'


Base = declarative_base(cls=DefaultBase)


class User(Base):
    id = Column(types.Integer, autoincrement=True, nullable=False, primary_key=True)
    name = Column(types.String, nullable=False)
    role = Column(types.Integer, nullable=True)
    is_active = Column(types.Boolean, nullable=False, default=True)
    created_at = Column(types.DateTime, nullable=False, default=datetime.datetime.utcnow)

    ADMIN = 64
    SUPERUSER = 128
    ADMINS = [ADMIN, SUPERUSER]


class AdminAccessLog(Base):
    id = Column(types.Integer, autoincrement=True, nullable=False, primary_key=True)
    user_id = Column(types.Integer, nullable=False)

    endpoint = Column(types.String, nullable=False)
    args = Column(types.String, nullable=True)
    form = Column(types.String, nullable=True)

    created_at = Column(types.DateTime, nullable=False, default=datetime.datetime.utcnow)
