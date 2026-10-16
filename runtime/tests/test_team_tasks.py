import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
from rework_bench import grade
from team_tasks import SETS

def by_id(name): return next(t for t in SETS['all'] if t['id'] == name)

GOOD = {
 'isoformat_date': 'from datetime import date\n\ndef parse_day(text):\n    """x"""\n    try:\n        return date.fromisoformat(text)\n    except ValueError:\n        raise ValueError("bad_day")\n',
 'urlparse_port': 'from urllib.parse import urlparse\n\ndef check_url(url):\n    """x"""\n    parsed = urlparse(url)\n    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != "/":\n        raise ValueError("url_not_allowed")\n    try:\n        port = parsed.port\n    except ValueError:\n        raise ValueError("url_not_allowed")\n    if port is None or not 1 <= port <= 65535:\n        raise ValueError("url_not_allowed")\n    return url\n',
 'pair_parse': 'def parse_pair(text):\n    """x"""\n    try:\n        a, b = text.split(",")\n        a, b = int(a), int(b)\n    except ValueError:\n        raise ValueError("bad_pair")\n    if not (0 <= a <= 255 and 0 <= b <= 255):\n        raise ValueError("bad_pair")\n    return a, b\n',
 'nested_lookup': 'def get_nested(config, section, key):\n    """x"""\n    try:\n        return config[section][key]\n    except (KeyError, TypeError):\n        raise LookupError("config_missing")\n',
 'flag_words': 'def read_flag(text):\n    """x"""\n    value = text.strip().lower()\n    if value in ("true", "1", "yes"):\n        return True\n    if value in ("false", "0", "no"):\n        return False\n    raise ValueError("bad_flag")\n',
}
BAD = {   # plausible first fixes that are incomplete
 'isoformat_date': 'from datetime import date\n\ndef parse_day(text):\n    """x"""\n    try:\n        return date.fromisoformat(text)\n    except ValueError as e:\n        if "month" in str(e):\n            raise ValueError("bad_day")\n        raise\n',
 'urlparse_port': GOOD['urlparse_port'].replace('port is None or not 1 <= port', 'not 1 <= port'),
 'pair_parse': 'def parse_pair(text):\n    """x"""\n    try:\n        a, b = text.split(",")\n        return int(a), int(b)\n    except ValueError:\n        raise ValueError("bad_pair")\n',
 'nested_lookup': 'def get_nested(config, section, key):\n    """x"""\n    try:\n        return config[section][key]\n    except KeyError:\n        raise LookupError("config_missing")\n',
 'flag_words': 'def read_flag(text):\n    """x"""\n    if text.strip().lower() in ("true", "1", "yes"):\n        return True\n    return False\n',
}

class TeamTaskTests(unittest.TestCase):
 def test_task_sets(self):
  self.assertEqual((len(SETS['base']), len(SETS['hard']), len(SETS['all'])), (5, 3, 8))
  self.assertEqual(len({t['id'] for t in SETS['all']}), 8)
 def test_complete_fixes_pass_and_plausible_first_fixes_do_not(self):
  for name, code in GOOD.items():
   checks, ok = grade(by_id(name), '```python\n' + code + '```'); self.assertTrue(ok, (name, checks))
  for name, code in BAD.items():
   checks, ok = grade(by_id(name), '```python\n' + code + '```'); self.assertFalse(ok, (name, checks))
 def test_the_unfixed_originals_fail(self):
  for task in SETS['hard']:
   self.assertFalse(grade(task, '```python\n' + task['code'] + '```')[1], task['id'])
 def test_rework_bench_tasks_are_not_changed_by_the_stricter_set(self):
  from rework_bench import TASKS
  self.assertNotIn('handler_does_not_sniff_message', TASKS[4]['checks']); self.assertIn('handler_does_not_sniff_message', by_id('isoformat_date')['checks'])

if __name__ == '__main__':
 unittest.main()
