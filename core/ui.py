import random
import ctypes
import pyautogui
from pywinauto import Desktop

VK_MAP = {'win': 0x5B, 'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10,
          'esc': 0x1B, 'enter': 0x0D, 'tab': 0x09}

# {'a': 65, 'b': 66, 'c': 67....}
VK_MAP.update({c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"})
KEYEVENTF_KEYUP = 0x0002

def sample_axis(start, stop, rng):
    """sampling in [start, stop); the weights of two sites are zero"""
    if stop - start < 3:
        raise ValueError("sampling area too small")

    positions = range(start, stop)

    weights = [
        ((p - start) * (stop - 1 - p)) ** 2
        for p in positions
    ]

    return rng.choices(positions, weights=weights, k=1)[0]

class UI:
    def __init__(self, timing, rng=None):
        self.timing = timing
        self.rng = rng if rng is not None else random.Random()
        self.desktop_icons = {}

    def fetch_desktop(self):
        # Locate the desktop icon list
        desktop = Desktop(backend="uia")
        icon_list = desktop.window(
            class_name="Progman"
        ).child_window(
            auto_id="1",
            control_type="List",
        ).wrapper_object()

        # Access the same list through the Win32 backend
        list_view = Desktop(backend="win32").window(
            handle=icon_list.handle
        ).wrapper_object()

        icons = {}

        for index in range(list_view.item_count()):
            item = list_view.get_item(index)
            name = item.text()

            # convert the icon bounds to screen coordinates
            rect = item.rectangle(area="icon")
            left, top = list_view.client_to_screen(
                (rect.left, rect.top)
            )
            right, bottom = list_view.client_to_screen(
                (rect.right, rect.bottom)
            )

            # Cache the bounds, without sampling a point yet
            icons[name] = (left, top, right, bottom)

        self.desktop_icons = icons

    def get_coords_desktop(self, element_id):
        left, top, right, bottom = self.desktop_icons[element_id]

        x = sample_axis(left, right, self.rng)
        y = sample_axis(top, bottom, self.rng)

        return x, y

    def move_and_click(self, x, y, button="left", end_x=None, end_y=None, scroll=0):
        # button: left, double, drag, scroll, middle, right.
        # For drag, (x, y) is the start and (end_x, end_y) is the end.
        # For scroll, positive values scroll up and negative values scroll down.
        if button not in ("left", "double", "drag", "scroll", "middle", "right"):
            raise ValueError("button must be left, double, drag, scroll, middle, or right")
        if button == "drag" and (end_x is None or end_y is None):
            raise ValueError("drag requires end_x and end_y")

        self.timing.delay()
        pyautogui.moveTo(x, y, duration=0.3)

        if button == "double":
            pyautogui.doubleClick(interval=0.1, button="left")
        elif button == "drag":
            pyautogui.mouseDown(button="left")
            try:
                pyautogui.moveTo(end_x, end_y, duration=0.3)
            finally:
                pyautogui.mouseUp(button="left")
        elif button == "scroll":
            pyautogui.scroll(scroll)
        else:
            pyautogui.click(button=button)

    def type_text(self, text):
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        window = user32.GetForegroundWindow()
        thread = user32.GetWindowThreadProcessId(ctypes.c_void_p(window), None)

        # Check English (0x09); Win+Space cycles through installed input languages.
        for _ in range(user32.GetKeyboardLayoutList(0, None)):
            if (user32.GetKeyboardLayout(thread) or 0) & 0x3FF == 0x09:
                break
            pyautogui.hotkey("win", "space")
            pyautogui.sleep(0.3)
        else:
            raise RuntimeError("Could not switch to an English keyboard")

        for char in text:
            self.timing.delay()
            pyautogui.write(char)

    def is_on_desktop(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        name = ctypes.create_unicode_buffer(64)
        ctypes.windll.user32.GetClassNameW(hwnd, name, 64)
        # name of the Desktop should be either Program or WorkerW
        return name.value in ("Progman", "WorkerW")

    def press_hotkey(self, *keys):
        # e.g. press_hotkey('win', 'd') to show desktop
        vks = [VK_MAP[k] for k in keys]
        for vk in vks:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            # release
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        self.timing.delay()
