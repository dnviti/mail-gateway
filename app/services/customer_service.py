import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer

logger = logging.getLogger(__name__)


async def get_customer_by_stripe_id(db: AsyncSession, stripe_customer_id: str) -> Customer | None:
    result = await db.execute(
        select(Customer).where(Customer.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one_or_none()
