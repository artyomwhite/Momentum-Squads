from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from typing import Annotated
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
class HelpdeskEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    event_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    ticket_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    customer_email: EmailStr
    message: ShortText
    reply_url: Annotated[str, StringConstraints(min_length=8, max_length=2048)]
class DraftResult(BaseModel):
    draft: str
    sources: list[dict]
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = True
