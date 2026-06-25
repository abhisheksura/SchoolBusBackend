from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.students.models import Parent, Student, StudentLeaveRequest, StudentParent
from app.core.enums import LeaveRequestStatus
from app.core.exceptions import (
    LeaveRequestNotFoundError,
    ParentNotFoundError,
    StudentNotFoundError,
)
from app.core.utils import utcnow


# =============================================================================
# Student Queries
# =============================================================================

async def get_student_by_student_id(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
) -> Student:
    """Fetch a student scoped to branch. Raises StudentNotFoundError if not found."""
    result = await db.execute(
        select(Student).where(
            Student.student_id == student_id,
            Student.school_id == school_id,
            Student.branch_id == branch_id,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise StudentNotFoundError(identifier=student_id)
    return student


async def get_student_by_user_id_or_none(
    db: AsyncSession,
    user_id: int,
) -> Student | None:
    """Fetch a student by user_id globally. Used to prevent duplicate user assignment."""
    result = await db.execute(
        select(Student).where(Student.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_students_by_branch(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Student], int]:
    """Fetch all students for a branch with pagination."""
    query = select(Student).where(
        Student.school_id == school_id,
        Student.branch_id == branch_id,
    )
    if active_only:
        query = query.where(Student.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Student.first_name, Student.last_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_students_by_branch_ids(
    db: AsyncSession,
    school_id: int,
    branch_ids: list[int],
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Student], int]:
    """Fetch students filtered to a list of branch_ids."""
    query = select(Student).where(
        Student.school_id == school_id,
        Student.branch_id.in_(branch_ids),
    )
    if active_only:
        query = query.where(Student.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Student.first_name, Student.last_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def get_all_students(
    db: AsyncSession,
    school_id: int | None,
    branch_id: int | None,
    limit: int,
    offset: int,
    active_only: bool = False,
) -> tuple[list[Student], int]:
    """
    DECOUPLED & OPTIMIZED: Completely removed DB joins for school/branch names.
    Now yields pure Student objects, delegating string enrichment to the service/cache.
    """
    # 1. Build common filter conditions
    filters = []
    if school_id is not None:
        filters.append(Student.school_id == school_id)
    if branch_id is not None:
        filters.append(Student.branch_id == branch_id)
    if active_only:
        filters.append(Student.is_active == True)

    # 2. Optimized direct Count (No subqueries, no string joins evaluated)
    total = await db.scalar(
        select(func.count(Student.student_id)).where(and_(*filters))
    ) or 0

    if total == 0:
        return [], 0

    # 3. Clean query fetching ONLY what this module owns
    query = select(Student).where(and_(*filters))

    result = await db.execute(
        query.order_by(Student.is_active.desc(), Student.grade, Student.section,
            Student.first_name, Student.last_name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total

async def create_student(
    db: AsyncSession,
    school_id: int,
    branch_id: int,
    first_name: str,
    last_name: str | None = None,
    admission_number: str | None = None,
    grade: str | None = None,
    section: str | None = None,
) -> Student:
    """Insert a new student record."""
    student = Student(
        school_id=school_id,
        branch_id=branch_id,
        first_name=first_name,
        last_name=last_name,
        admission_number=admission_number,
        grade=grade,
        section=section,
    )
    db.add(student)
    await db.flush()
    await db.refresh(student)
    return student


async def update_student_by_student_id(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    **kwargs,
) -> Student:
    """Update student fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Student)
        .where(
            Student.student_id == student_id,
            Student.school_id == school_id,
            Student.branch_id == branch_id,
        )
        .values(**values)
        .returning(Student)
    )
    await db.flush()
    student = result.scalar_one_or_none()
    if not student:
        raise StudentNotFoundError(identifier=student_id)
    return student


async def deactivate_student_by_student_id(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
) -> Student:
    result = await db.execute(
        update(Student)
        .where(
            Student.student_id == student_id,
            Student.school_id == school_id,
            Student.branch_id == branch_id,
        )
        .values(
            is_active=False,
            updated_at=func.now(),
        )
    )
    await db.flush()

    if result.rowcount == 0:
        raise StudentNotFoundError(identifier=student_id)

    return await get_student_by_student_id(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
    )


async def reactivate_student_by_student_id(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
) -> Student:
    result = await db.execute(
        update(Student)
        .where(
            Student.student_id == student_id,
            Student.school_id == school_id,
            Student.branch_id == branch_id,
        )
        .values(
            is_active=True,
            updated_at=func.now(),
        )
    )

    await db.flush()

    if result.rowcount == 0:
        raise StudentNotFoundError(identifier=student_id)

    return await get_student_by_student_id(
        db=db,
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
    )

# =============================================================================
# Parent Queries
# =============================================================================

async def get_parent_by_parent_id(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
) -> Parent:
    """Fetch a parent scoped to school. Raises ParentNotFoundError if not found."""
    result = await db.execute(
        select(Parent).where(
            Parent.parent_id == parent_id,
            Parent.school_id == school_id,
        )
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise ParentNotFoundError(identifier=parent_id)
    return parent


async def get_parent_by_user_id_or_none(
    db: AsyncSession,
    user_id: int,
) -> Parent | None:
    """Fetch a parent by user_id globally. Used to prevent duplicate user assignment."""
    result = await db.execute(
        select(Parent).where(Parent.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_parents_by_school(
    db: AsyncSession,
    school_id: int,
    limit: int,
    offset: int,
    active_only: bool = True,
) -> tuple[list[Parent], int]:
    """Fetch all parents for a school with pagination."""
    query = select(Parent).where(Parent.school_id == school_id)
    if active_only:
        query = query.where(Parent.is_active == True)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Parent.first_name, Parent.last_name).limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


async def create_parent(
    db: AsyncSession,
    school_id: int,
    user_id: int,
    first_name: str,
    last_name: str | None = None,
    phone: str | None = None,
    alternate_phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
) -> Parent:
    """Insert a new parent record."""
    parent = Parent(
        school_id=school_id,
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        alternate_phone=alternate_phone,
        email=email,
        address=address,
    )
    db.add(parent)
    await db.flush()
    await db.refresh(parent)
    return parent


async def update_parent_by_parent_id(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
    **kwargs,
) -> Parent:
    """Update parent fields. Uses RETURNING — single round-trip."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(Parent)
        .where(
            Parent.parent_id == parent_id,
            Parent.school_id == school_id,
        )
        .values(**values)
        .returning(Parent)
    )
    await db.flush()
    parent = result.scalar_one_or_none()
    if not parent:
        raise ParentNotFoundError(identifier=parent_id)
    return parent


async def deactivate_parent_by_parent_id(
    db: AsyncSession,
    parent_id: int,
    school_id: int,
) -> Parent:
    """Soft-delete a parent. Uses RETURNING — single round-trip."""
    result = await db.execute(
        update(Parent)
        .where(
            Parent.parent_id == parent_id,
            Parent.school_id == school_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(Parent)
    )
    await db.flush()
    parent = result.scalar_one_or_none()
    if not parent:
        raise ParentNotFoundError(identifier=parent_id)
    return parent


# =============================================================================
# StudentParent Queries
# =============================================================================

async def get_student_parent_by_id(
    db: AsyncSession,
    student_parent_id: int,
    student_id: int,
) -> StudentParent:
    """Fetch a student-parent link. Raises StudentNotFoundError if not found."""
    result = await db.execute(
        select(StudentParent).where(
            StudentParent.student_parent_id == student_parent_id,
            StudentParent.student_id == student_id,
        )
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise StudentNotFoundError(identifier=student_parent_id)
    return sp


async def get_student_parent_by_student_and_parent(
    db: AsyncSession,
    student_id: int,
    parent_id: int,
) -> StudentParent | None:
    """Fetch existing link between a student and parent. Returns None if not linked."""
    result = await db.execute(
        select(StudentParent).where(
            StudentParent.student_id == student_id,
            StudentParent.parent_id == parent_id,
        )
    )
    return result.scalar_one_or_none()


async def get_parents_by_student_id(
    db: AsyncSession,
    student_id: int,
) -> list[StudentParent]:
    """Fetch all parent links for a student."""
    result = await db.execute(
        select(StudentParent)
        .where(StudentParent.student_id == student_id)
        .order_by(StudentParent.is_primary.desc(), StudentParent.created_at)
    )
    return list(result.scalars().all())


async def create_student_parent(
    db: AsyncSession,
    student_id: int,
    parent_id: int,
    relationship: str,
    is_primary: bool = False,
) -> StudentParent:
    """Create a student-parent link."""
    sp = StudentParent(
        student_id=student_id,
        parent_id=parent_id,
        relationship=relationship,
        is_primary=is_primary,
    )
    db.add(sp)
    await db.flush()
    await db.refresh(sp)
    return sp


async def update_student_parent_by_id(
    db: AsyncSession,
    student_parent_id: int,
    student_id: int,
    **kwargs,
) -> StudentParent:
    """Update a student-parent link. Uses RETURNING."""
    values = dict(kwargs)
    values["updated_at"] = func.now()

    result = await db.execute(
        update(StudentParent)
        .where(
            StudentParent.student_parent_id == student_parent_id,
            StudentParent.student_id == student_id,
        )
        .values(**values)
        .returning(StudentParent)
    )
    await db.flush()
    sp = result.scalar_one_or_none()
    if not sp:
        raise StudentNotFoundError(identifier=student_parent_id)
    return sp


async def delete_student_parent_by_id(
    db: AsyncSession,
    student_parent_id: int,
    student_id: int,
) -> None:
    """
    Hard-delete a student-parent link.
    Removing the link is not a soft-delete — it means the parent is no longer
    associated with this student.
    """
    result = await db.execute(
        delete(StudentParent).where(
            StudentParent.student_parent_id == student_parent_id,
            StudentParent.student_id == student_id,
        )
    )
    await db.flush()
    if result.rowcount == 0:
        raise StudentNotFoundError(identifier=student_parent_id)


# =============================================================================
# StudentLeaveRequest Queries
# =============================================================================

async def get_leave_request_by_leave_id(
    db: AsyncSession,
    leave_id: int,
    student_id: int,
    school_id: int,
) -> StudentLeaveRequest:
    """Fetch a leave request. Raises LeaveRequestNotFoundError if not found."""
    result = await db.execute(
        select(StudentLeaveRequest).where(
            StudentLeaveRequest.leave_id == leave_id,
            StudentLeaveRequest.student_id == student_id,
            StudentLeaveRequest.school_id == school_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise LeaveRequestNotFoundError(identifier=leave_id)
    return leave


async def get_all_leave_requests_by_student(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    limit: int,
    offset: int,
    status_filter: LeaveRequestStatus | None = None,
) -> tuple[list[StudentLeaveRequest], int]:
    """Fetch all leave requests for a student with optional status filter."""
    query = select(StudentLeaveRequest).where(
        StudentLeaveRequest.student_id == student_id,
        StudentLeaveRequest.school_id == school_id,
    )
    if status_filter:
        query = query.where(StudentLeaveRequest.status == status_filter.value)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(StudentLeaveRequest.start_date.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def create_leave_request(
    db: AsyncSession,
    student_id: int,
    school_id: int,
    branch_id: int,
    start_date,
    end_date,
    requested_by: int | None = None,
    reason: str | None = None,
) -> StudentLeaveRequest:
    """Insert a new leave request. Status defaults to PENDING."""
    leave = StudentLeaveRequest(
        student_id=student_id,
        school_id=school_id,
        branch_id=branch_id,
        requested_by=requested_by,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
    )
    db.add(leave)
    await db.flush()
    await db.refresh(leave)
    return leave


async def update_leave_request_status(
    db: AsyncSession,
    leave_id: int,
    student_id: int,
    school_id: int,
    new_status: LeaveRequestStatus,
) -> StudentLeaveRequest:
    """
    Update the status of a leave request.
    Uses RETURNING — single round-trip.
    Caller must validate the transition before calling this.
    """
    result = await db.execute(
        update(StudentLeaveRequest)
        .where(
            StudentLeaveRequest.leave_id == leave_id,
            StudentLeaveRequest.student_id == student_id,
            StudentLeaveRequest.school_id == school_id,
        )
        .values(status=new_status.value)
        .returning(StudentLeaveRequest)
    )
    await db.flush()
    leave = result.scalar_one_or_none()
    if not leave:
        raise LeaveRequestNotFoundError(identifier=leave_id)
    return leave