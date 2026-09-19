import ctypes

VK_MAP = {'win': 0x5B, 'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10,
          'esc': 0x1B, 'enter': 0x0D, 'tab': 0x09}

# {'a': 65, 'b': 66, 'c': 67....}
VK_MAP.update({c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"})
KEYEVENTF_KEYUP = 0x0002


class UI:
    def __init__(self, timing):
        self.timing = timing

    def get_coords(self, element_id):
        # to get coordinates of elements on the screen
        # NEEDSWORK: what mechanism will we be using?
        return (500, 500)

    def move_and_click(self, x, y):
        # this part of logic should be *extremly important*
        # since bypassing process monitor isn't that hard, but making
        # mouse movement look like human behavior is.

        # NEEDSWORK:
        # 1. cursor should move along a curve..?
        self.timing.delay()
        print(f"move and click: ({x}, {y})")

    def type_text(self, text):
        for char in text:
            self.timing.delay()
            # NEEDSWORK:
            #
            # 1. random typo?
            #
            # 2. it's common for we human to stop typing and start
            # thinking now and then... perhaps we need to simulate
            # that, too.
            print(f"typing: {char}")

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