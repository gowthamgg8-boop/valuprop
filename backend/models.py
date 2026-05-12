"""
ValUprop.in — Database Models
backend/models.py

Tables: users, properties, valuations, payments, events
Matches PRD section 5.2 schema exactly.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """Lead captured from free estimate page."""
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    phone        = Column(String(20), nullable=True, index=True)
    email        = Column(String(255), nullable=True, index=True)
    ip           = Column(String(64), nullable=True)
    source       = Column(String(100), nullable=True)   # utm_source
    utm_campaign = Column(String(100), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    properties = relationship("Property", back_populates="user")


class Property(Base):
    """Submitted property details."""
    __tablename__ = "properties"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    type         = Column(String(50))    # Apartment | IndependentHouse | Villa | LandPlot
    address      = Column(String(500))
    city         = Column(String(100))
    locality     = Column(String(200))
    pincode      = Column(String(10))
    area_data    = Column(JSON)          # Full form submission as JSON
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user       = relationship("User", back_populates="properties")
    valuations = relationship("Valuation", back_populates="property")


class Valuation(Base):
    """Free and paid valuation results."""
    __tablename__ = "valuations"

    id           = Column(Integer, primary_key=True, index=True)
    property_id  = Column(Integer, ForeignKey("properties.id"), nullable=True)
    tier         = Column(String(10))     # "free" | "paid"
    status       = Column(String(20))     # "pending" | "ready" | "error"
    value_min    = Column(Float, nullable=True)   # in Lakhs
    value_max    = Column(Float, nullable=True)
    confidence   = Column(Integer, nullable=True)  # 0-100
    insights     = Column(JSON, nullable=True)     # Teaser (free) or full 7-section report (paid)
    llm_response = Column(JSON, nullable=True)     # Raw LLM JSON for debugging
    generated_at = Column(DateTime, nullable=True)

    # OWASP A01 fix — access token bound to this paid valuation.
    # Generated at /api/payment/verify success; required on every paid
    # report read (/api/valuation/paid/{id}, /api/report/{id}/pdf).
    # NULL on free valuations.
    access_token = Column(String(64), nullable=True, index=True)

    property = relationship("Property", back_populates="valuations")
    payments = relationship("Payment", back_populates="valuation",
                            foreign_keys="Payment.valuation_id")


class Payment(Base):
    """Razorpay payment records."""
    __tablename__ = "payments"

    id                  = Column(Integer, primary_key=True, index=True)
    valuation_id        = Column(Integer, ForeignKey("valuations.id"))
    paid_valuation_id   = Column(Integer, ForeignKey("valuations.id"), nullable=True)
    razorpay_order_id   = Column(String(100), unique=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature  = Column(String(300), nullable=True)
    amount              = Column(Integer)          # In paise
    status              = Column(String(20))       # created | paid | failed | refunded
    paid_at             = Column(DateTime, nullable=True)
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    valuation = relationship("Valuation", back_populates="payments",
                             foreign_keys=[valuation_id])


class Event(Base):
    """Funnel analytics events."""
    __tablename__ = "events"

    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=True)
    event_name = Column(String(100))    # page_view | form_submit | estimate_viewed | payment_started | payment_success
    properties = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Report(Base):
    """Generated PDF reports stored in S3."""
    __tablename__ = "reports"

    id           = Column(Integer, primary_key=True, index=True)
    valuation_id = Column(Integer, ForeignKey("valuations.id"), unique=True)
    s3_key       = Column(String(300), nullable=True)   # e.g. "reports/VUP-00001.pdf"
    emailed_at   = Column(DateTime, nullable=True)
    sent_to_email= Column(String(255), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
