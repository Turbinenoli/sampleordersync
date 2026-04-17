from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()
engine = create_engine(
    "sqlite:///database/lims_data.db", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String, default="user")
    department = Column(String)
    language_set = Column(String, default="de")
    is_active = Column(Boolean, default=False)
    password_reset_requested = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    orders = relationship("Order", back_populates="user")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True)
    project_name = Column(String)
    psp_element = Column(String)
    project_type = Column(String, nullable=True)
    status = Column(String, default="cat_order_inbox")
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    result_file_blob = Column(LargeBinary, nullable=True)
    result_file_name = Column(String, nullable=True)


    customer_note = Column(String, nullable=True)
    lab_note = Column(String, nullable=True)

    user = relationship("User", back_populates="orders")
    samples = relationship(
        "Sample", back_populates="order", cascade="all, delete-orphan"
    )
    logs = relationship(
        "OrderLog", back_populates="order", cascade="all, delete-orphan"
    )


class OrderLog(Base):
    """NEU: Audit Trail für Statusänderungen."""

    __tablename__ = "order_logs"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    timestamp = Column(DateTime, default=datetime.now)
    action = Column(String)  # z.B. "Status geändert"
    status_from = Column(String)
    status_to = Column(String)
    changed_by = Column(String)  # Name des Bearbeiters

    order = relationship("Order", back_populates="logs")


class Sample(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    customer_sample_name = Column(String)
    material_type = Column(String)
    cat_preparation = Column(String)
    cat_analyses = Column(String)
    external_id = Column(String, nullable=True)
    order = relationship("Order", back_populates="samples")

    __table_args__ = (
        UniqueConstraint(
            "order_id", "customer_sample_name", name="_sample_name_order_uc"
        ),
    )


def init_db():
    Base.metadata.create_all(bind=engine)


    session = SessionLocal()
    try:

        session.execute(text("ALTER TABLE orders ADD COLUMN customer_note TEXT"))
        session.execute(text("ALTER TABLE orders ADD COLUMN lab_note TEXT"))

        session.execute(
            text(
                "ALTER TABLE users ADD COLUMN password_reset_requested BOOLEAN DEFAULT 0"
            )
        )
        session.execute(
            text("ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE")
        )
        session.execute(text("ALTER TABLE orders ADD COLUMN project_type TEXT"))
        session.execute(text("ALTER TABLE samples ADD COLUMN cat_preparation TEXT"))
        session.execute(text("ALTER TABLE users ADD COLUMN language_set TEXT"))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
