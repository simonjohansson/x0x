"""Run the stock-free suite; missing prerequisites cannot count as acceptance."""
import unittest

from .cpu import ROOT


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests/host'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.skipped:
        print('Required checks skipped:', result.skipped)
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == '__main__':
    raise SystemExit(main())
