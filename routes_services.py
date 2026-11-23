from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from database.services_queries import list_services, save_service, delete_service

router = APIRouter()
BASE_DIR = Path(__file__).parent


def require_admin(request: Request):
    if not request.session.get("staff_user"):
        raise HTTPException(status_code=401, detail="Please log in.")
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")


class ServiceIn(BaseModel):
    name: str
    description: str = ""
    price: float


def check(result):
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/staff/services")
def services_page(request: Request):
    if not request.session.get("staff_user"):
        return RedirectResponse(url="/staff/login", status_code=303)
    if request.session.get("role") != "admin":
        return RedirectResponse(url="/staff", status_code=303)
    return FileResponse(BASE_DIR / "static" / "staff_services.html")


@router.get("/staff/api/services")
def services_list(request: Request):
    require_admin(request)
    return list_services()


@router.post("/staff/api/services")
def services_create(data: ServiceIn, request: Request):
    require_admin(request)
    return check(save_service(data.name, data.description, data.price))


@router.put("/staff/api/services/{service_id}")
def services_update(service_id: int, data: ServiceIn, request: Request):
    require_admin(request)
    return check(save_service(data.name, data.description, data.price, service_id))


@router.delete("/staff/api/services/{service_id}")
def services_delete(service_id: int, request: Request):
    require_admin(request)
    return check(delete_service(service_id))