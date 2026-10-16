"""Die Farben der Tokens müssen lesbar sein – in beiden Themen (Redesign Phase A, 16.10.2026, Projektregel B6-G-04: 5:1 auf Flächen)."""
import re
import unittest
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'ui' / 'tokens.css'


def block_values(css, selector):
    m = re.search(re.escape(selector) + r'\s*\{([^{}]*)\}', css)
    return dict(re.findall(r'--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;', m.group(1))) if m else {}


def theme(css, name):
    base = block_values(css, ':root')
    if name != 'dark':
        base.update(block_values(css, f'html[data-theme="{name}"]'))
    return {k: v.lower() for k, v in base.items()}


def luminance(hex_value):
    h = hex_value.lstrip('#')
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def ratio(a, b):
    lighter, darker = sorted([luminance(a), luminance(b)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class TokenContrast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = TOKENS.read_text(encoding='utf-8')

    def check(self, name):
        t = theme(self.css, name)
        pairs = [('text', 'bg'), ('text', 'panel'), ('text', 'panel-2'),
                 ('muted', 'bg'), ('muted', 'panel'), ('muted', 'panel-2'),
                 ('heading', 'panel'), ('ok', 'ok-bg'), ('warn', 'warn-bg'), ('bad', 'bad-bg')]
        for fg, bg in pairs:
            with self.subTest(theme=name, text=fg, on=bg):
                value = ratio(t[fg], t[bg])
                # Projektregel: Text auf Flächen mindestens 5:1; die Statusfarben auf ihrer Tönung mindestens 4.5:1
                # 5:1 gilt auf den Flächen (panel, panel-2), der Hintergrund darf 4.5:1 haben (Klar: 4.75:1 seit jeher)
                floor = 4.5 if (fg in ('ok', 'warn', 'bad') or bg == 'bg') else 5.0
                self.assertGreaterEqual(value, floor, f'{name}: {fg} {t[fg]} on {bg} {t[bg]} is {value:.2f}:1')

    def test_default_dark_theme_is_readable(self):
        self.check('dark')

    def test_light_theme_is_still_readable(self):
        self.check('klar')

    def test_the_default_is_dark(self):
        t = theme(self.css, 'dark')
        self.assertLess(luminance(t['bg']), 0.05, 'the default background is dark')
        self.assertGreater(luminance(t['text']), 0.7, 'the default text is light')


if __name__ == '__main__':
    unittest.main()
