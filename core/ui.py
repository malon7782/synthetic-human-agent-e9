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