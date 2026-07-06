from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    message: str


class WaitlistCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    consent_to_updates: bool
    website: str = Field(default="", max_length=0, description="Honeypot field")


class ContactCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=5_000)
    website: str = Field(default="", max_length=0, description="Honeypot field")


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=12)


class PreferencesUpdate(BaseModel):
    timezone: str | None = None
    notifications_enabled: bool | None = None


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1_000)
    parameters: dict[str, Any] = Field(default_factory=dict)


class StrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1_000)
    parameters: dict[str, Any] | None = None


class BacktestCreate(BaseModel):
    strategy_id: str
    symbols: list[str] = Field(min_length=1, max_length=100)
    start_at: datetime
    end_at: datetime
    initial_cash: float = Field(gt=0)


class AgentRunCreate(BaseModel):
    mode: Literal["research", "paper"] = "research"
    symbols: list[str] = Field(min_length=1, max_length=100)


class BrokerConnectionCreate(BaseModel):
    provider: str
    authorization_code: str


class OrderPreviewRequest(BaseModel):
    broker_connection_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    order_type: Literal["market", "limit"]
    limit_price: float | None = Field(default=None, gt=0)


class OrderCreate(OrderPreviewRequest):
    preview_id: str
    risk_acknowledged: bool
