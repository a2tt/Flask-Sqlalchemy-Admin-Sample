from sqlalchemy import create_engine

from project.models.base import Base
import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
Base.metadata.create_all(engine)
