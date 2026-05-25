from datetime import datetime
from typing import Optional

from app.domain.attention import ProgramLike, program_needs_attention


def program_attention_state(program: ProgramLike, now: Optional[datetime] = None) -> str:
    if not program.program_status.is_operational:
        return "Inactive"
    return "Needs attention" if program_needs_attention(program, now=now) else "OK"
