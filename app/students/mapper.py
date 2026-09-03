from app.students.models import Student
from app.students.schemas import StudentSummary


def to_student_summary(student: Student) -> StudentSummary:
    primary_parent = next(
        (
            sp
            for sp in student.student_parents
            if sp.is_primary and sp.parent is not None
        ),
        None,
    )

    parent_name = None
    parent_phone = None

    if primary_parent:
        parent = primary_parent.parent
        parent_name = f"{parent.first_name} {parent.last_name or ''}".strip()
        parent_phone = parent.phone

    return StudentSummary(
        student_id=student.student_id,
        first_name=student.first_name,
        last_name=student.last_name,
        admission_number=student.admission_number,
        grade=student.grade,
        section=student.section,
        parent_name=parent_name,
        parent_phone=parent_phone,
    )