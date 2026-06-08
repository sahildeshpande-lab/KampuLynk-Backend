import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invitation_code_id = Column(
        String(36),
        ForeignKey("invitation_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    originator_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_email = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    invitation_code = relationship("InvitationCode", back_populates="invitations")
    originator = relationship("User", back_populates="sent_invitations", foreign_keys=[originator_user_id])
