from fastapi import APIRouter

# -----------------------------------------------------------------------------
# Domain routers are imported here as they are built.
# Uncomment each line once the domain router file is created.
# -----------------------------------------------------------------------------
from app.api.v1.auth           import router as auth_router
from app.api.v1.schools        import router as schools_router
from app.api.v1.fleet          import router as fleet_router
from app.api.v1.drivers        import router as drivers_router
from app.api.v1.gps            import router as gps_router
from app.api.v1.routes         import router as routes_router
from app.api.v1.trips          import router as trips_router
from app.api.v1.students       import router as students_router
from app.api.v1.assignments    import router as assignments_router
from app.api.v1.attendance     import router as attendance_router
# from app.notifications.router import router as notifications_router

api_router = APIRouter(prefix="/api/v1")

# -----------------------------------------------------------------------------
# Register domain routers
# Each domain gets its own prefix and tags for clean OpenAPI grouping.
# -----------------------------------------------------------------------------
api_router.include_router(auth_router,          prefix="/auth",          tags=["Auth"])
api_router.include_router(schools_router,       prefix="/schools",       tags=["Schools"])
api_router.include_router(fleet_router,         prefix="/fleet",         tags=["Fleet"])
api_router.include_router(drivers_router,       tags=["Drivers"])
api_router.include_router(gps_router,           tags=["GPS"])
api_router.include_router(routes_router,        tags=["Routes"])
api_router.include_router(trips_router,         tags=["Trips"])
api_router.include_router(students_router,      tags=["Students"])
api_router.include_router(assignments_router,   tags=["Assignments"])
api_router.include_router(attendance_router,    tags=["Attendance"])
# api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])