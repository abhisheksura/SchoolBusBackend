from fastapi import APIRouter

# -----------------------------------------------------------------------------
# Domain routers are imported here as they are built.
# Uncomment each line once the domain router file is created.
# -----------------------------------------------------------------------------
# from app.auth.router         import router as auth_router
# from app.schools.router      import router as schools_router
# from app.branches.router     import router as branches_router
# from app.fleet.router        import router as fleet_router
# from app.routes.router       import router as routes_router
# from app.trips.router        import router as trips_router
# from app.students.router     import router as students_router
# from app.attendance.router   import router as attendance_router
# from app.notifications.router import router as notifications_router

api_router = APIRouter(prefix="/api/v1")

# -----------------------------------------------------------------------------
# Register domain routers
# Each domain gets its own prefix and tags for clean OpenAPI grouping.
# -----------------------------------------------------------------------------
# api_router.include_router(auth_router,          prefix="/auth",          tags=["Auth"])
# api_router.include_router(schools_router,       prefix="/schools",       tags=["Schools"])
# api_router.include_router(branches_router,      prefix="/branches",      tags=["Branches"])
# api_router.include_router(fleet_router,         prefix="/fleet",         tags=["Fleet"])
# api_router.include_router(routes_router,        prefix="/routes",        tags=["Routes"])
# api_router.include_router(trips_router,         prefix="/trips",         tags=["Trips"])
# api_router.include_router(students_router,      prefix="/students",      tags=["Students"])
# api_router.include_router(attendance_router,    prefix="/attendance",    tags=["Attendance"])
# api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
