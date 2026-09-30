from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from app.core.database_pool import db_pool


async def _session():
    # Reuse the global pool; creating a new engine per request leaks connections.
    if not db_pool.session_factory:
        await db_pool.initialize()
    if not db_pool.session_factory:
        raise Exception("Database pool not available")
    return db_pool.get_session()


async def calculate_total_revenue(
    property_id: str, tenant_id: str, month: Optional[int] = None, year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Aggregates revenue from database, optionally for one calendar month.

    Month boundaries are evaluated in the property's local timezone, not UTC:
    a check-in at 2024-02-29 23:30 UTC is March 1st in Europe/Paris.
    """
    query = text("""
        SELECT
            COALESCE(SUM(r.total_amount), 0) AS total_revenue,
            COUNT(r.id) AS reservation_count
        FROM reservations r
        JOIN properties p ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        WHERE r.property_id = :property_id AND r.tenant_id = :tenant_id
        AND (
            CAST(:month AS INTEGER) IS NULL
            OR (
                EXTRACT(MONTH FROM r.check_in_date AT TIME ZONE p.timezone) = :month
                AND EXTRACT(YEAR FROM r.check_in_date AT TIME ZONE p.timezone) = :year
            )
        )
    """)

    async with await _session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "month": month,
            "year": year,
        })
        row = result.fetchone()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(Decimal(str(row.total_revenue))),
        "currency": "USD",
        "count": row.reservation_count,
    }


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a specific month in the property's local timezone.
    """
    result = await calculate_total_revenue(property_id, tenant_id, month, year)
    return Decimal(result["total"])


async def get_tenant_properties(tenant_id: str) -> List[Dict[str, Any]]:
    """Lists the properties that belong to a tenant."""
    query = text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY id")
    async with await _session() as session:
        result = await session.execute(query, {"tenant_id": tenant_id})
        return [dict(row._mapping) for row in result]
