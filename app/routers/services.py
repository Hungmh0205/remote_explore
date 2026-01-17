import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class ServiceInfo(BaseModel):
    name: str
    display_name: str
    status: str
    start_type: Optional[str] = None

@router.get("/services", response_model=List[ServiceInfo])
def list_services():
    """List all Windows services."""
    services = []
    # psutil.win_service_iter() returns a generator of WindowsService
    services = []
    try:
        for svc in psutil.win_service_iter():
            try:
                # Manually accessing properties instead of using as_dict which is failing
                services.append(ServiceInfo(
                    name=svc.name(),
                    display_name=svc.display_name(),
                    status=svc.status(),
                    start_type=svc.start_type() if hasattr(svc, 'start_type') else None
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                try:
                    # Fallback for restricted services
                    services.append(ServiceInfo(
                        name=svc.name(),
                        display_name=svc.display_name(),
                        status=svc.status(),
                        start_type=None
                    ))
                except:
                    pass
            except Exception:
                pass
    except Exception as e:
        print(f"Error accessing Service Manager: {e}")
        return []

    return sorted(services, key=lambda s: s.name.lower())


class ServiceActionBody(BaseModel):
    action: str  # start, stop, restart

@router.post("/services/{name}")
def manage_service(name: str, body: ServiceActionBody):
    """Start, stop, or restart a service."""
    try:
        svc = psutil.win_service_get(name)
        action = body.action.lower()
        
        if action == "start":
            svc.start()
        elif action == "stop":
            svc.stop()
        elif action == "restart":
            svc.restart()
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        return {"ok": True, "status": svc.status()}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Service not found")
    except psutil.AccessDenied:
         raise HTTPException(status_code=403, detail="Access denied. Run as Administrator.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
