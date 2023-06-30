from sqlalchemy import create_engine, Column, String, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import numpy as np
import setting

Base = declarative_base()


class GameInfoTable(Base):
    __tablename__ = "game_info"

    channel_id = Column(String(255), primary_key=True)
    channel_name = Column(String(255))
    customer_email = Column(String(255))
    sales_email = Column(String(255))
    customer_id = Column(String(255))
    sales_id = Column(String(255))
    is_liar = Column(Boolean)
    master_row_index = Column(Integer)
    case_id = Column(Integer)
    is_started = Column(Boolean, default=False)
    worksheet_url = Column(String(255), default="")
    judge = Column(String(255), default="")
    reason = Column(String(255), default="")
    customer_done = Column(Boolean, default=False)
    sales_done = Column(Boolean, default=False)

    def __repr__(self):
        return f"<GameInfoTable(channel_id={self.channel_id}, customer_email={self.customer_email}, sales_email={self.sales_email}, customer_id={self.customer_id}, sales_id={self.sales_id}, is_started={self.is_started})>"


class GameInfoDB:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        db_url = f"mysql+mysqlconnector://{setting.MYSQL_USER}:{setting.MYSQL_PASSWORD}@{setting.MYSQL_HOST}/{setting.MYSQL_DATABASE}"
        self.engine = create_engine(db_url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.Session = scoped_session(self.session_factory)
        self.create_table()
    

    def create_table(self):
        Base.metadata.create_all(self.engine)

    def save_game_info(self, **kwargs):
        try:
            for key, value in kwargs.items():
                if isinstance(value, np.int64):
                    kwargs[key] = int(value)
                    
            session = self.Session()
            channel_id = kwargs.get('channel_id')
            game_info = session.query(GameInfoTable).filter_by(channel_id=channel_id).first()
            if game_info:
                # If a record with the given channel_id exists, delete it
                session.delete(game_info)
            game_info = GameInfoTable(**kwargs)
            session.add(game_info)
            session.commit()
            self.Session.remove()
            return game_info
        except Exception as e:
            session.rollback()
            return e
        finally:
            self.Session.remove()
            
    def get_game_info(self, channel_id):
        session = self.Session()
        game_info = session.query(GameInfoTable).filter_by(channel_id=channel_id).first()
        self.Session.remove()
        return game_info

    def get_is_started(self, channel_id):
        session = self.Session()
        is_started = session.query(GameInfoTable.is_started).filter_by(channel_id=channel_id).first()
        self.Session.remove()
        return is_started
    
    def set_started(self, channel_id):
        session = self.Session()
        session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"is_started": True})
        session.commit()
        self.Session.remove()
    
    def set_judge(self, channel_id, judge):
        session = self.Session()
        session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"judge": judge})
        session.commit()
        self.Session.remove()
    
    def set_worksheet_url(self, channel_id, worksheet_url):
        session = self.Session()
        session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"worksheet_url": worksheet_url})
        session.commit()
        self.Session.remove()
    
    def set_customer_done(self, channel_id, undo=False):
        session = self.Session()
        if undo:
            session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"customer_done": False})
        else:
            session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"customer_done": True})
        session.commit()
        self.Session.remove()
    
    def set_sales_done(self, channel_id, undo=False):
        session = self.Session()
        if undo:
            session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"sales_done": False})
        else:
            session.query(GameInfoTable).filter_by(channel_id=channel_id).update({"sales_done": True})
        session.commit()
        self.Session.remove()