import importlib
import sys
import types
import unittest


def install_gi_stubs():
    gi = types.ModuleType("gi")
    gi.require_version = lambda *_args: None

    repository = types.ModuleType("gi.repository")

    class FakeAlign:
        CENTER = "center"
        FILL = "fill"

    class FakeOrientation:
        VERTICAL = "vertical"
        HORIZONTAL = "horizontal"

    class FakePolicyType:
        NEVER = "never"
        AUTOMATIC = "automatic"

    class FakeSelectionMode:
        NONE = "none"

    class FakeBox:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.children = []

        def add(self, child):
            self.children.append(child)

        def remove(self, child):
            self.children.remove(child)

        def get_children(self):
            return list(self.children)

        def get_spacing(self):
            return self.kwargs.get("spacing", 0)

    class FakeLabel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.attributes = None
            self.markup = None
            self.text = kwargs.get("label")

        def set_attributes(self, attributes):
            self.attributes = attributes

        def set_markup(self, markup):
            self.markup = markup

        def set_text(self, text):
            self.text = text

    class FakeImage:
        def __init__(self):
            self.pixbuf = None
            self.connected_signals = []

        def set_halign(self, *_args):
            pass

        def set_hexpand(self, *_args):
            pass

        def set_from_pixbuf(self, pixbuf):
            self.pixbuf = pixbuf

        def connect(self, *args):
            self.connected_signals.append(args)

    class FakeButton:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.connected_signals = []
            self.label = FakeLabel(label=kwargs.get("label"))
            self.style_context = types.SimpleNamespace(add_class=lambda *_args: None)

        def connect(self, *args):
            self.connected_signals.append(args)

        def get_children(self):
            return [self.label]

        def get_style_context(self):
            return self.style_context

    class FakePixbuf:
        def __init__(self, width=100, height=80):
            self.width = width
            self.height = height

        def get_width(self):
            return self.width

        def get_height(self):
            return self.height

    class FakeMemoryInputStream:
        @classmethod
        def new_from_data(cls, *_args):
            return cls()

        def close_async(self, *_args):
            pass

    class FakeFlowBox(FakeBox):
        def set_max_children_per_line(self, *_args):
            pass

        def set_min_children_per_line(self, *_args):
            pass

    class FakeScrolledWindow(FakeBox):
        def set_hexpand(self, *_args):
            pass

        def set_vexpand(self, *_args):
            pass

        def set_policy(self, *_args):
            pass

        def connect(self, *_args):
            pass

    class FakeGrid(FakeBox):
        def attach(self, child, *_args):
            self.add(child)

    Gtk = types.SimpleNamespace(
        Align=FakeAlign,
        Box=FakeBox,
        Button=FakeButton,
        FlowBox=FakeFlowBox,
        Grid=FakeGrid,
        Image=FakeImage,
        Label=FakeLabel,
        Orientation=FakeOrientation,
        PolicyType=FakePolicyType,
        ScrolledWindow=FakeScrolledWindow,
        SelectionMode=FakeSelectionMode,
    )

    class FakeAttrList:
        def __init__(self):
            self.attributes = []

        def insert(self, attribute):
            self.attributes.append(attribute)

    Pango = types.SimpleNamespace(
        AttrList=FakeAttrList,
        attr_scale_new=lambda scale: ("scale", scale),
    )

    repository.Gdk = types.SimpleNamespace(keyval_name=lambda _keyval: "")
    repository.GdkPixbuf = types.SimpleNamespace(
        Pixbuf=types.SimpleNamespace(
            new_from_stream=lambda *_args: FakePixbuf(),
            new_from_stream_at_scale=lambda _stream, width, height, _preserve: FakePixbuf(
                width, height
            ),
        )
    )
    repository.Gio = types.SimpleNamespace(MemoryInputStream=FakeMemoryInputStream)
    repository.Gtk = Gtk
    repository.Pango = Pango

    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = repository


install_gi_stubs()
prompts = importlib.import_module("ks_includes.widgets.prompts")


class FakeScreen:
    def __init__(self):
        self.gtk = types.SimpleNamespace(Button=prompts.Gtk.Button)
        self.apiclient = types.SimpleNamespace(send_request=lambda *_args, **_kwargs: b"image")
        self._send_action = lambda *_args, **_kwargs: None


class PromptMarkupTest(unittest.TestCase):
    def test_prompt_content_is_vertically_centered(self):
        prompt = prompts.Prompt(FakeScreen())

        self.assertEqual(prompts.Gtk.Align.CENTER, prompt.scroll_box.kwargs["valign"])

    def test_prompt_markup_adds_markup_label(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode("prompt_markup <b><span foreground='#4ade80'>Ready</span></b>")

        self.assertEqual(1, len(prompt.scroll_box.children))
        self.assertEqual(
            "<b><span foreground='#4ade80'>Ready</span></b>",
            prompt.scroll_box.children[0].markup,
        )

    def test_prompt_row_groups_image_and_markup(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode("prompt_row_start")
        prompt.decode("prompt_image config/images/spool.svg")
        prompt.decode("prompt_markup <b>Blue PLA</b>")
        prompt.decode("prompt_row_end")

        self.assertEqual(1, len(prompt.scroll_box.children))
        row = prompt.scroll_box.children[0]
        self.assertEqual(prompts.Gtk.Orientation.HORIZONTAL, row.kwargs["orientation"])
        self.assertEqual(prompts.Gtk.Align.FILL, row.kwargs["halign"])
        self.assertEqual(5, row.kwargs["spacing"])
        self.assertTrue(row.kwargs["homogeneous"])
        self.assertIsInstance(row.children[0], prompts.Gtk.Image)
        self.assertEqual("<b>Blue PLA</b>", row.children[1].markup)

    def test_prompt_image_scales_to_viewport_allocation(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode("prompt_image config/images/spool.svg")
        image = prompt.scroll_box.children[0]

        prompt._load_images(None, types.SimpleNamespace(width=300, height=200))

        self.assertEqual(250, image.pixbuf.get_width())
        self.assertEqual(200, image.pixbuf.get_height())

    def test_prompt_row_image_scales_to_padded_row_cell_width(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode("prompt_row_start")
        prompt.decode("prompt_image config/images/green_checkmark.svg")
        prompt.decode("prompt_markup <b>Blue PLA</b>")
        prompt.decode("prompt_image config/images/blue_filament.svg")
        prompt.decode("prompt_row_end")

        row = prompt.scroll_box.children[0]
        prompt._load_images(None, types.SimpleNamespace(width=900, height=300))

        self.assertEqual(277, row.children[0].pixbuf.get_width())
        self.assertEqual(222, row.children[0].pixbuf.get_height())
        self.assertEqual(277, row.children[2].pixbuf.get_width())
        self.assertEqual(222, row.children[2].pixbuf.get_height())

    def test_prompt_button_markup_sets_inline_button_label_markup(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode("prompt_button_markup <span foreground='#facc15'>Heat</span>|M104 S220|warning")

        button = prompt.scroll_box.children[0]
        self.assertEqual("<span foreground='#facc15'>Heat</span>", button.label.markup)
        self.assertEqual("dialog-warning", button.kwargs["style"])

    def test_prompt_footer_button_markup_stores_label_markup(self):
        prompt = prompts.Prompt(FakeScreen())

        prompt.decode(
            "prompt_footer_button_markup <span foreground='#38bdf8'>Continue</span>|M117 ok|primary"
        )

        self.assertEqual(
            {
                "name": "<span foreground='#38bdf8'>Continue</span>",
                "response": 1,
                "gcode": "M117 ok",
                "style": "dialog-primary",
                "markup": True,
            },
            prompt.buttons[0],
        )

    def test_prompt_footer_button_markup_applies_to_dialog_button_label(self):
        prompt = prompts.Prompt(FakeScreen())
        button = prompts.Gtk.Button(label="<span foreground='#38bdf8'>Continue</span>")
        prompt.buttons.append(
            {
                "name": "<span foreground='#38bdf8'>Continue</span>",
                "response": 1,
                "gcode": "M117 ok",
                "style": "dialog-primary",
                "markup": True,
            }
        )
        prompt.prompt = types.SimpleNamespace(get_widget_for_response=lambda _response: button)

        prompt._apply_footer_button_markup()

        self.assertEqual("<span foreground='#38bdf8'>Continue</span>", button.label.markup)


if __name__ == "__main__":
    unittest.main()
