from fastapi import APIRouter

from database.queries import get_departments, get_all_doctors, get_services

router = APIRouter()


@router.get("/api/public/departments")
def public_departments():
    return get_departments()


@router.get("/api/public/doctors")
def public_doctors():
    return get_all_doctors()


@router.get("/api/public/services")
def public_services():
    rows = get_services()
    result = []
    for row in rows:
        item = dict(row)
        item["price"] = float(item["price"]) if item["price"] is not None else None
        result.append(item)
    return result