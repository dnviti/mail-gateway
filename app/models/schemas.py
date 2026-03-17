from pydantic import BaseModel


class WebhookResponse(BaseModel):
    status: str
    message: str


class CustomerBase(BaseModel):
    email: str
    name: str | None = None
    stripe_customer_id: str


class CustomerCreate(CustomerBase):
    pass
