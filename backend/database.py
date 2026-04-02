from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./pentex.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Device(Base):
    __tablename__ = "devices"

    id          = Column(Integer, primary_key=True, index=True)
    ip          = Column(String, unique=True, index=True)
    mac         = Column(String, default="Unknown")
    hostname    = Column(String, default="Unknown")
    vendor      = Column(String, default="Unknown")
    protocol    = Column(String, default="Wi-Fi")   # Wi-Fi | Zigbee | Matter
    os_guess    = Column(String, default="Unknown")
    risk_level  = Column(String, default="UNKNOWN")  # SAFE | MEDIUM | RISK
    risk_score  = Column(Float, default=0.0)
    open_ports  = Column(String, default="")         # comma-separated
    last_seen   = Column(DateTime, default=datetime.utcnow)

    vulnerabilities = relationship("Vulnerability", back_populates="device", cascade="all, delete-orphan")


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id          = Column(Integer, primary_key=True, index=True)
    device_id   = Column(Integer, ForeignKey("devices.id"))
    vuln_type   = Column(String)       # e.g. DEFAULT_PASSWORD | OPEN_TELNET | WEAK_ENCRYPTION
    severity    = Column(String)       # LOW | MEDIUM | HIGH | CRITICAL
    description = Column(String)
    port        = Column(Integer, nullable=True)
    protocol    = Column(String, nullable=True)

    device = relationship("Device", back_populates="vulnerabilities")


class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id          = Column(Integer, primary_key=True, index=True)
    uid         = Column(String, unique=True, index=True)
    card_type   = Column(String, default="Unknown") # Mifare, NFC, EM4100
    sak         = Column(String, default="")        # SAK value for Mifare
    data        = Column(String, default="")        # Dump of data if readable
    risk_level  = Column(String, default="UNKNOWN") # SAFE | RISK
    risk_score  = Column(Float, default=0.0)
    last_seen   = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"

    key   = Column(String, primary_key=True, index=True)
    value = Column(String)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Initialize default settings if missing
    db = SessionLocal()
    if not db.query(Setting).filter(Setting.key == "simulation_mode").first():
        db.add(Setting(key="simulation_mode", value="true"))
    if not db.query(Setting).filter(Setting.key == "nmap_timeout").first():
        db.add(Setting(key="nmap_timeout", value="60"))
    db.commit()
    db.close()
