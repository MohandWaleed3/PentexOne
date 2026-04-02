from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class VulnerabilityOut(BaseModel):
    id: int
    vuln_type: str
    severity: str
    description: str
    port: Optional[int] = None
    protocol: Optional[str] = None

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    id: int
    ip: str
    mac: str
    hostname: str
    vendor: str
    protocol: str
    os_guess: str
    risk_level: str
    risk_score: float
    open_ports: str
    last_seen: datetime
    vulnerabilities: List[VulnerabilityOut] = []

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    network: str = "192.168.1.0/24"
    timeout: int = 60


class ScanStatus(BaseModel):
    status: str
    message: str
    devices_found: int = 0


class ReportSummary(BaseModel):
    total_devices: int
    safe_count: int
    medium_count: int
    risk_count: int
    unknown_count: int
    scan_time: datetime

class RFIDCardOut(BaseModel):
    id: int
    uid: str
    card_type: str
    sak: str
    data: str
    risk_level: str
    risk_score: float
    last_seen: datetime

    class Config:
        from_attributes = True

class SettingUpdate(BaseModel):
    simulation_mode: Optional[str] = None
    nmap_timeout: Optional[str] = None
