"""UI package exports."""

from cert_coach.ui.console import (
    console,
    error_console,
    is_interactive,
    print_error,
    print_info,
    print_step,
    print_warning,
)
from cert_coach.ui.mascot import play_mascot_animation, render_static_welcome
from cert_coach.ui.prompts import (
    prompt_database_location,
    prompt_exam_selection,
    prompt_harness_selection,
)

__all__ = [
    "console",
    "error_console",
    "is_interactive",
    "play_mascot_animation",
    "print_error",
    "print_info",
    "print_step",
    "print_warning",
    "prompt_database_location",
    "prompt_exam_selection",
    "prompt_harness_selection",
    "render_static_welcome",
]
