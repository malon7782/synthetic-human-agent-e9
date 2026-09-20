import ctypes

import pyautogui


class UI:
    def __init__(self, timing):
        self.timing = timing

    def get_coords(self, element_id):
        # to get coordinates of elements on the screen
        # NEEDSWORK: what mechanism will we be using?
        return (500, 500)

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
