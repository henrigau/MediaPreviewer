import unittest

from media_preview.hyprland import SpaceBinder, _class_from_event


class HyprlandTests(unittest.TestCase):
    def test_activewindow_event_class(self):
        self.assertEqual(_class_from_event("activewindow>>nemo,Home"), "nemo")
        self.assertEqual(_class_from_event("activewindow>>org.kde.dolphin,Downloads"), "org.kde.dolphin")
        self.assertIsNone(_class_from_event("openwindow>>abc"))

    def test_supported_classes(self):
        binder = SpaceBinder()
        self.assertTrue(binder.should_bind_for_class("nemo"))
        self.assertTrue(binder.should_bind_for_class("io.github.henri.MediaPreview"))
        self.assertFalse(binder.should_bind_for_class("kitty"))


if __name__ == "__main__":
    unittest.main()

