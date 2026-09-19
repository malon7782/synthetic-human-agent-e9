import random
from pywinauto import Desktop


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

    def get_coords(self, element_id=None):
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

        results = []

        for index in range(list_view.item_count()):
            item = list_view.get_item(index)
            name = item.text()

            # Skip items that do not match the requested name
            if element_id is not None and name != element_id:
                continue

            # convert the icon bounds to screen coordinates
            rect = item.rectangle(area="icon")
            left, top = list_view.client_to_screen(
                (rect.left, rect.top)
            )
            right, bottom = list_view.client_to_screen(
                (rect.right, rect.bottom)
            )

            # Sample a point inside the icon bounds
            x = sample_axis(left, right, self.rng)
            y = sample_axis(top, bottom, self.rng)

            results.append({
                "name": name,
                "coords": (x, y),
                "icon_rect": (left, top, right, bottom),
            })
        return results

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

# get_coor_test, random return 10 coords from desktop


if __name__ == "__main__":
    import time
    from pywinauto import mouse

    ui = UI(timing=None)

    print("Show the desktop within 3 seconds.")
    time.sleep(3)

    icons = ui.get_coords()

    if not icons:
        print("No desktop items found.")
    else:
        previous = None

        for _ in range(10):
            candidates = [icon for icon in icons if icon is not previous]
            icon = random.choice(candidates or icons)

            print(icon["name"], icon["coords"])
            mouse.move(coords=icon["coords"])
            previous = icon
            time.sleep(3)
