from src.scenes import Scene


class Test(Scene):
    def on_start(self):
        super().on_start()
        self.run_tests()


    def run_tests(self) -> None:
        for name in dir(self):
            if name.startswith('test'):
                attr = getattr(self, name)
                if callable(attr):
                    attr()


    def p(
        self,
        msg: str,
        *,
        bold: bool = False,
        color: str | None = None,
        center: bool = False,
        width: int = 40,
        raw: bool = False,
    ):
        """Print a message with optional ANSI formatting.

        - `bold`: bold text
        - `color`: one of black, red, green, yellow, blue, magenta, cyan, white
        - `center`: center text within `width`
        - `raw`: print exactly `msg` without formatting
        - `width`: width for centering (default 40)
        """
        if raw:
            print(msg)
            return

        colors = {
            "black": "\033[30m",
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
        }
        bold_code = "\033[1m" if bold else ""
        color_code = colors.get(color.lower(), "") if color else ""
        reset = "\033[0m" if (bold_code or color_code) else ""

        out = msg
        if center:
            out = out.center(width)

        print(f"{bold_code}{color_code}{out}{reset}")

    
    def space_line(self, l: int = 40):
        self.p('\n*' + '-' * l + '*\n', color='yellow')


    def print_title(self, title: str = "TESTS", color: str | None = None, width: int = 40):
        """Print a decorated title using the `p` helper for formatting."""
        self.space_line(width)
        self.p(title, bold=True, color=color, center=True, width=width)
        self.space_line(width)


    def print_subtitle(self, subtitle: str, color: str | None = None, width: int = 40):
        """Print a decorated subtitle using the `p` helper for formatting."""
        self.p(subtitle, bold=True, color=color, center=True, width=width)
        self.p('-' * width, color=color)
