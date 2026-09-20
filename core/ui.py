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
