"""Unit tests for UI components, mascot frames, and console helpers."""

from __future__ import annotations

import unittest

from cert_coach.ui.console import print_error, print_info, print_step, print_warning
from cert_coach.ui.mascot import (
    OWL_ANIMATION_FRAMES,
    WING_STYLES,
    render_owl_panel,
    render_static_welcome,
)


class UiTests(unittest.TestCase):
    def test_owl_frames_defined(self) -> None:
        self.assertGreaterEqual(len(OWL_ANIMATION_FRAMES), 5)
        for eyes, wing, status, subtitle, duration in OWL_ANIMATION_FRAMES:
            self.assertTrue(len(eyes.strip()) > 0)
            self.assertIn(wing, WING_STYLES)
            self.assertTrue(len(status.strip()) > 0)
            self.assertGreater(duration, 0)

    def test_wing_styles_defined(self) -> None:
        for style_name in ("rest", "up", "out", "wave"):
            self.assertIn(style_name, WING_STYLES)
            self.assertEqual(len(WING_STYLES[style_name]), 4)

    def test_render_owl_panel(self) -> None:
        for wing in WING_STYLES:
            panel = render_owl_panel(eyes=" ◕ ", wing=wing, status="Testing", subtitle="Test Subtitle")
            self.assertIsNotNone(panel)

    def test_console_helpers_run_without_exceptions(self) -> None:
        print_step("Test Step", "detail")
        print_info("Test Info")
        print_warning("Test Warning")
        print_error("Test Error")
        render_static_welcome()


if __name__ == "__main__":
    unittest.main()
