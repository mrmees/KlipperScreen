import importlib
import sys
import types
import unittest


def install_gi_stubs():
    gi = types.ModuleType("gi")
    gi.require_version = lambda *_args: None

    repository = types.ModuleType("gi.repository")

    class FakeStyleContext:
        def __init__(self):
            self.classes = []

        def add_class(self, style_class):
            self.classes.append(style_class)

    class FakeLabel:
        def set_line_wrap_mode(self, *_args):
            pass

        def set_line_wrap(self, *_args):
            pass

        def set_ellipsize(self, *_args):
            pass

        def set_lines(self, *_args):
            pass

    class FakeContainer:
        def get_children(self):
            return []

    class FakeButton(FakeContainer):
        def __init__(self):
            self.children = [FakeLabel()]
            self.size_request = None
            self.style_context = FakeStyleContext()

        def get_children(self):
            return self.children

        def set_size_request(self, width, height):
            self.size_request = width, height

        def get_style_context(self):
            return self.style_context

    class FakeActionArea:
        def __init__(self):
            self.layout = None

        def set_layout(self, layout):
            self.layout = layout

    class FakeContentArea:
        def __init__(self):
            self.children = []

        def set_margin_start(self, *_args):
            pass

        def set_margin_end(self, *_args):
            pass

        def set_margin_top(self, *_args):
            pass

        def set_margin_bottom(self, *_args):
            pass

        def add(self, child):
            self.children.append(child)

    class FakeDialog:
        def __init__(self, title, *_args, **_kwargs):
            self.title = title
            self.size_request = None
            self.action_area = FakeActionArea()
            self.content_area = FakeContentArea()
            self.style_context = FakeStyleContext()
            self.buttons = {}
            self.connections = []

        def set_size_request(self, width, height):
            self.size_request = width, height

        def fullscreen(self):
            pass

        def get_action_area(self):
            return self.action_area

        def add_button(self, _name, response):
            self.buttons[response] = FakeButton()

        def get_widget_for_response(self, response):
            return self.buttons[response]

        def connect(self, *args):
            self.connections.append(args)

        def get_style_context(self):
            return self.style_context

        def get_content_area(self):
            return self.content_area

        def show_all(self):
            pass

        def get_window(self):
            return None

        def get_title(self):
            return self.title

        def get_size(self):
            return self.size_request

    class FakeScrolledWindow:
        def __init__(self, **_kwargs):
            pass

        def add_events(self, *_args):
            pass

        def get_vscrollbar(self):
            return types.SimpleNamespace(
                get_style_context=lambda: types.SimpleNamespace(add_class=lambda *_args: None)
            )

    class FakeButtonBoxStyle:
        EXPAND = "expand"

    class FakeEventMask:
        BUTTON_PRESS_MASK = 1
        TOUCH_MASK = 2
        BUTTON_RELEASE_MASK = 4

    Gtk = types.SimpleNamespace(
        Alignment=FakeContainer,
        Bin=FakeContainer,
        Box=FakeContainer,
        Button=FakeButton,
        ButtonBoxStyle=FakeButtonBoxStyle,
        Container=FakeContainer,
        Dialog=FakeDialog,
        Label=FakeLabel,
        PositionType=types.SimpleNamespace(TOP="top"),
        ScrolledWindow=FakeScrolledWindow,
    )
    Pango = types.SimpleNamespace(
        EllipsizeMode=types.SimpleNamespace(END="end"),
        WrapMode=types.SimpleNamespace(WORD_CHAR="word-char"),
    )
    repository.Gdk = types.SimpleNamespace(EventMask=FakeEventMask, Window=object)
    repository.GdkPixbuf = types.SimpleNamespace()
    repository.Gio = types.SimpleNamespace()
    repository.Gtk = Gtk
    repository.Pango = Pango

    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = repository


install_gi_stubs()
sys.modules.pop("ks_includes.KlippyGtk", None)
klippygtk = importlib.import_module("ks_includes.KlippyGtk")


class FakeScreen:
    def __init__(self):
        self.dialogs = []
        self.lock_screen = types.SimpleNamespace(reset_timeout=lambda *_args: None)
        self.screensaver = types.SimpleNamespace(reset_timeout=lambda *_args: None)
        self.show_cursor = True
        self.windowed = True


class DialogButtonLayoutTest(unittest.TestCase):
    def make_gtk(self):
        gtk = klippygtk.KlippyGtk.__new__(klippygtk.KlippyGtk)
        gtk.screen = FakeScreen()
        gtk.width = 1200
        gtk.height = 720
        gtk.dialog_buttons_height = 144
        gtk.set_cursor = lambda **_kwargs: None
        return gtk

    def test_footer_buttons_expand_evenly_for_each_supported_button_count(self):
        for button_count in range(1, 5):
            with self.subTest(button_count=button_count):
                gtk = self.make_gtk()
                buttons = [
                    {"name": f"Button {index}", "response": index, "style": "dialog-info"}
                    for index in range(button_count)
                ]

                dialog = gtk.Dialog("Title", buttons, object(), lambda *_args: None)

                self.assertEqual(klippygtk.Gtk.ButtonBoxStyle.EXPAND, dialog.action_area.layout)
                for button in dialog.buttons.values():
                    self.assertEqual((-1, gtk.dialog_buttons_height), button.size_request)


if __name__ == "__main__":
    unittest.main()
