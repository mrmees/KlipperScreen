import logging
import math
from urllib.parse import quote

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango


class Prompt:
    ROW_IMAGE_PADDING = 10
    ROW_SPACING = 5

    def __init__(self, screen):
        self.screen = screen
        self.gtk = screen.gtk
        self.window_title = "KlipperScreen"
        self.text = self.header = ""
        self.buttons = []
        self.id = 1
        self.prompt = None
        self.scroll_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
        )
        self.groups = []
        self.rows = []
        self.images = []
        self.image_scale = None
        self.text_scale = 1

    def _key_press_event(self, widget, event):
        keyval_name = Gdk.keyval_name(event.keyval)
        if keyval_name in ["Escape", "BackSpace"]:
            self.close()

    def decode(self, data):
        logging.info(f"{data}")
        if data.startswith("prompt_begin"):
            self.header = data.replace("prompt_begin", "")
            self.window_title = self.header if self.header else "KlipperScreen"
            self.text = ""
            self.buttons = []
            self.groups = []
            self.rows = []
            self.images = []
            self.id = 1
            self.image_scale = None
            self.text_scale = 1
            for child in self.scroll_box.get_children():
                self.scroll_box.remove(child)
            return
        elif data.startswith("prompt_image_scale "):
            self.set_image_scale(data.replace("prompt_image_scale ", "", 1))
            return
        elif data.startswith("prompt_text_scale "):
            self.set_text_scale(data.replace("prompt_text_scale ", "", 1))
            return
        elif data.startswith("prompt_markup"):
            markup = data[len("prompt_markup ") :] if data.startswith("prompt_markup ") else ""
            if markup:
                self.set_markup(markup)
            else:
                self.text_scale = 1
            return
        elif data.startswith("prompt_text"):
            self.text = data[len("prompt_text ") :] if data.startswith("prompt_text ") else ""
            if self.text:
                self.set_text()
            else:
                self.text_scale = 1
            return
        elif data.startswith("prompt_image "):
            self.set_image(data.replace("prompt_image ", "", 1))
            return
        elif data.startswith("prompt_button_markup "):
            data = data.replace("prompt_button_markup ", "")
            params = data.split("|")
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error("Unexpected number of parameters on the button")
                return
            self.set_button(*params, markup=True)
            return
        elif data.startswith("prompt_button "):
            data = data.replace("prompt_button ", "")
            params = data.split("|")
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error("Unexpected number of parameters on the button")
                return
            self.set_button(*params)
            return
        elif data.startswith("prompt_footer_button_markup"):
            data = data.replace("prompt_footer_button_markup ", "")
            params = data.split("|")
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error("Unexpected number of parameters on the button")
                return
            self.set_footer_button(*params, markup=True)
            return
        elif data.startswith("prompt_footer_button"):
            data = data.replace("prompt_footer_button ", "")
            params = data.split("|")
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error("Unexpected number of parameters on the button")
                return
            self.set_footer_button(*params)
            return
        elif data == "prompt_show":
            if not self.prompt:
                self.show()
            return
        elif data == "prompt_end":
            self.end()
        elif data == "prompt_button_group_start":
            self.groups.append(
                Gtk.FlowBox(
                    selection_mode=Gtk.SelectionMode.NONE,
                    orientation=Gtk.Orientation.HORIZONTAL,
                )
            )
        elif data == "prompt_button_group_end":
            if self.groups:
                self._add_content(self.groups.pop())
        elif data == "prompt_row_start":
            self.rows.append(
                Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL,
                    spacing=self.ROW_SPACING,
                    homogeneous=True,
                    halign=Gtk.Align.FILL,
                    hexpand=True,
                    vexpand=False,
                )
            )
        elif data == "prompt_row_end":
            if self.rows:
                row = self.rows.pop()
                self._add_content(row)
        else:
            logging.debug(f"Unknown option {data}")

    def _add_content(self, widget):
        parent = self.rows[-1] if self.rows else self.scroll_box
        parent.add(widget)
        return parent

    @staticmethod
    def _get_moonraker_resource(path):
        path = path.strip().replace("\\", "/")
        parts = [part for part in path.split("/") if part]
        if (
            path.startswith(("/", "~"))
            or len(parts) < 2
            or any(part in {".", ".."} or ":" in part for part in parts)
        ):
            return None
        return "/".join(parts)

    @staticmethod
    def _parse_scale(scale, default=1):
        if not scale:
            return default
        try:
            scale = float(scale)
        except ValueError:
            return default
        if not math.isfinite(scale) or scale <= 0:
            return default
        return scale

    @staticmethod
    def _get_image_size(width, height, scale, max_width, max_height):
        ratio = min(max_width / width, max_height / height) * (scale or 1)
        width *= ratio
        height *= ratio
        return max(round(width), 1), max(round(height), 1)

    @staticmethod
    def _get_stream_image_pixbuf(data, path, width=-1, height=-1):
        stream = Gio.MemoryInputStream.new_from_data(data, None)
        try:
            if width > 0 and height > 0:
                return GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, width, height, True)
            return GdkPixbuf.Pixbuf.new_from_stream(stream)
        except Exception as e:
            logging.exception(e)
            logging.error(f"Unable to load prompt image: {path}")
            return None
        finally:
            stream.close_async(2)

    def _get_scaled_image_pixbuf(self, image_data, scale, max_width, max_height):
        data, resource, width, height = image_data
        width, height = self._get_image_size(width, height, scale, max_width, max_height)
        return self._get_stream_image_pixbuf(data, resource, width, height)

    def _get_image_limits(self, prompt_image, allocation):
        max_width = max(allocation.width, 1)
        max_height = max(allocation.height, 1)
        parent = prompt_image["parent"]
        if parent is not self.scroll_box:
            children = parent.get_children()
            child_count = max(len(children), 1)
            get_allocated_width = getattr(parent, "get_allocated_width", None)
            if callable(get_allocated_width):
                allocated_width = get_allocated_width()
                if allocated_width > 1:
                    max_width = allocated_width
            get_spacing = getattr(parent, "get_spacing", None)
            spacing = get_spacing() if callable(get_spacing) else 0
            cell_width = max((max_width - spacing * (child_count - 1)) / child_count, 1)
            max_width = max(cell_width - self.ROW_IMAGE_PADDING * 2, 1)
        return max_width, max_height

    def _load_image(self, prompt_image, max_width, max_height):
        limits = max(round(max_width), 1), max(round(max_height), 1)
        if prompt_image["limits"] == limits:
            return
        prompt_image["limits"] = limits
        pixbuf = self._get_scaled_image_pixbuf(
            prompt_image["image_data"], prompt_image["scale"], *limits
        )
        if pixbuf is None:
            prompt_image["parent"].remove(prompt_image["image"])
            if prompt_image in self.images:
                self.images.remove(prompt_image)
            return
        prompt_image["image"].set_from_pixbuf(pixbuf)

    def _load_images(self, _widget, allocation):
        for prompt_image in self.images.copy():
            max_width, max_height = self._get_image_limits(prompt_image, allocation)
            self._load_image(prompt_image, max_width, max_height)

    def set_image_scale(self, scale):
        self.image_scale = self._parse_scale(scale, default=None)

    def set_image(self, path):
        path = path.strip()
        image_scale = self.image_scale
        self.image_scale = None
        if not path:
            logging.error("Prompt image path is empty")
            return
        resource = self._get_moonraker_resource(path)
        if resource is None:
            logging.error(f"Invalid prompt image path: {path}")
            return
        data = self.screen.apiclient.send_request(
            f"server/files/{quote(resource, safe='/')}", json=False
        )
        if data is False:
            logging.error(f"Unable to load prompt image: {resource}")
            return
        pixbuf = self._get_stream_image_pixbuf(data, resource)
        if pixbuf is None:
            return
        image = Gtk.Image()
        image.set_halign(Gtk.Align.CENTER)
        image.set_hexpand(True)
        image.set_from_pixbuf(pixbuf)
        parent = self._add_content(image)
        image_data = (data, resource, pixbuf.get_width(), pixbuf.get_height())
        prompt_image = {
            "image": image,
            "image_data": image_data,
            "scale": image_scale,
            "parent": parent,
            "limits": None,
        }
        self.images.append(prompt_image)

    def set_text_scale(self, scale):
        self.text_scale = self._parse_scale(scale)

    def _apply_text_scale(self, label):
        if self.text_scale != 1:
            attributes = Pango.AttrList()
            attributes.insert(Pango.attr_scale_new(self.text_scale))
            label.set_attributes(attributes)
        self.text_scale = 1

    def set_text(self):
        label = Gtk.Label(label=self.text, wrap=True, hexpand=True, vexpand=True)
        self._apply_text_scale(label)
        self._add_content(label)

    def set_markup(self, markup):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        try:
            label.set_markup(markup)
        except Exception as e:
            logging.exception(e)
            logging.error(f"Invalid prompt markup: {markup}")
            label.set_text(markup)
        self._apply_text_scale(label)
        self._add_content(label)

    @staticmethod
    def _set_button_markup(button, markup):
        label = Prompt._find_widget(button, Gtk.Label)
        if label is None:
            return
        try:
            label.set_markup(markup)
        except Exception as e:
            logging.exception(e)
            logging.error(f"Invalid prompt button markup: {markup}")
            label.set_text(markup)

    @staticmethod
    def _find_widget(widget, wanted_type):
        if isinstance(widget, wanted_type):
            return widget
        get_children = getattr(widget, "get_children", None)
        if not callable(get_children):
            return None
        for child in get_children():
            result = Prompt._find_widget(child, wanted_type)
            if result is not None:
                return result
        return None

    def set_button(self, name, gcode, style="default", markup=False):
        button = self.gtk.Button(image_name=None, label=f"{name}", style=f"dialog-{style}")
        if markup:
            self._set_button_markup(button, name)
        button.connect(
            "clicked", self.screen._send_action, "printer.gcode.script", {"script": gcode}
        )
        if self.groups:
            self.groups[-1].add(button)
            # Workaround to expand the buttons horizontally
            max_childs = len(self.groups[-1].get_children())
            self.groups[-1].set_max_children_per_line(min(4, max_childs))
            self.groups[-1].set_min_children_per_line(min(4, max_childs))
        else:
            self._add_content(button)

    def set_footer_button(self, name, gcode, style="default", markup=False):
        button = {"name": name, "response": self.id, "gcode": gcode, "style": f"dialog-{style}"}
        if markup:
            button["markup"] = True
        self.buttons.append(button)
        self.id += 1

    def _apply_footer_button_markup(self):
        for button in self.buttons:
            if not button.get("markup"):
                continue
            dialog_button = self.prompt.get_widget_for_response(button["response"])
            self._set_button_markup(dialog_button, button["name"])

    def show(self):
        logging.info(f"Prompt {self.header} {self.text} {self.buttons}")

        title = Gtk.Label(
            wrap=True, hexpand=True, vexpand=False, halign=Gtk.Align.CENTER, label=self.header
        )

        close = self.gtk.Button("cancel", scale=self.gtk.bsidescale)
        close.set_hexpand(False)
        close.set_vexpand(False)
        close.connect("clicked", self.close)

        scroll = self.gtk.ScrolledWindow(steppers=False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.connect("size-allocate", self._load_images)
        scroll.add(self.scroll_box)

        content = Gtk.Grid(hexpand=True, vexpand=True)
        scroll_row = 0
        if not self.screen.windowed:
            content.attach(title, 0, 0, 1, 1)
            content.attach(close, 1, 0, 1, 1)
            scroll_row = 1
        content.attach(scroll, 0, scroll_row, 2, 1)

        self.prompt = self.gtk.Dialog(
            self.window_title,
            self.buttons,
            content,
            self.response,
        )
        self._apply_footer_button_markup()
        self.prompt.connect("key-press-event", self._key_press_event)
        self.prompt.connect("delete-event", self.close)
        self.screen.screensaver.close()

    def response(self, dialog, response_id):
        for button in self.buttons:
            if button["response"] == response_id:
                self.screen._send_action(None, "printer.gcode.script", {"script": button["gcode"]})

    def close(self, *args):
        script = {"script": 'RESPOND type="command" msg="action:prompt_end"'}
        self.screen._send_action(None, "printer.gcode.script", script)

    def end(self):
        if self.prompt is not None:
            self.gtk.remove_dialog(self.prompt)
        self.prompt = None
        self.screen.prompt = None
