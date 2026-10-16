import unittest
import datetime
from guppi_runtime.agent_manager.code_meter import daily_totals, heatmap, cards

class TestCodeMeter(unittest.TestCase):
    
    def test_empty_records(self):
        self.assertEqual(daily_totals([]), {})
    
    def test_valid_records(self):
        records = [
            {"date": "2023-01-01", "author": "guppi", "added": 10},
            {"date": "2023-01-01", "author": "claude", "added": 5},
            {"date": "2023-01-02", "author": "guppi", "added": 3}
        ]
        expected = {
            "2023-01-01": {"guppi": 10, "claude": 5},
            "2023-01-02": {"guppi": 3, "claude": 0}
        }
        self.assertEqual(daily_totals(records), expected)
    
    def test_invalid_records_skipped(self):
        records = [
            {"date": "2023-01-01", "author": "guppi", "added": 10},
            {"date": "2023-01-02", "author": "invalid", "added": 5},  # Invalid author
            {"date": "2023-01-03", "author": "claude", "added": 3},
            {"date": "invalid-date", "author": "guppi", "added": 2},  # Invalid date
            {"date": "2023-01-04", "author": "claude", "added": -1},  # Negative added
            {"date": "2023-01-05", "author": "guppi", "added": 7},  # Valid
        ]
        expected = {
            "2023-01-01": {"guppi": 10, "claude": 0},
            "2023-01-03": {"guppi": 0, "claude": 3},
            "2023-01-05": {"guppi": 7, "claude": 0}
        }
        self.assertEqual(daily_totals(records), expected)
    
    def test_float_added_not_valid(self):
        records = [
            {"date": "2023-01-01", "author": "guppi", "added": 10.5},  # Float not valid
            {"date": "2023-01-01", "author": "claude", "added": 5},  # Valid
        ]
        expected = {
            "2023-01-01": {"guppi": 0, "claude": 5}
        }
        self.assertEqual(daily_totals(records), expected)
    
    def test_bool_added_not_valid(self):
        records = [
            {"date": "2023-01-01", "author": "guppi", "added": True},  # Bool not valid
            {"date": "2023-01-01", "author": "claude", "added": 5},  # Valid
        ]
        expected = {
            "2023-01-01": {"guppi": 0, "claude": 5}
        }
        self.assertEqual(daily_totals(records), expected)
    
    def test_missing_added_field(self):
        records = [
            {"date": "2023-01-01", "author": "guppi"},  # Missing 'added'
            {"date": "2023-01-01", "author": "claude", "added": 5},  # Valid
        ]
        expected = {
            "2023-01-01": {"guppi": 0, "claude": 5}
        }
        self.assertEqual(daily_totals(records), expected)
    
    def test_date_normalization(self):
        records = [
            {"date": "2023-01-01", "author": "guppi", "added": 10},
            {"date": "2023-01-02", "author": "claude", "added": 5},
        ]
        result = daily_totals(records)
        # Check that dates are in proper ISO format
        self.assertIn("2023-01-01", result)
        self.assertIn("2023-01-02", result)
    
    def test_sorted_dates(self):
        records = [
            {"date": "2023-01-03", "author": "guppi", "added": 10},
            {"date": "2023-01-01", "author": "claude", "added": 5},
            {"date": "2023-01-02", "author": "guppi", "added": 3},
        ]
        result = daily_totals(records)
        keys = list(result.keys())
        self.assertEqual(keys, ["2023-01-01", "2023-01-02", "2023-01-03"])

    def test_heatmap_empty(self):
        result = heatmap({}, "2023-01-01", 2)
        self.assertEqual(len(result), 7)  # 7 days of week
        self.assertEqual(len(result[0]), 2)  # 2 weeks
        for row in result:
            for cell in row:
                self.assertTrue(cell is None or (cell["lines"] == 0 and cell["level"] == 0))

    def test_heatmap_with_data(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},  # Sunday
            "2023-01-02": {"guppi": 3, "claude": 0},   # Monday
            "2023-01-03": {"guppi": 0, "claude": 7},   # Tuesday
        }
        result = heatmap(daily, "2023-01-03", 2)
        self.assertEqual(len(result), 7)
        self.assertEqual(len(result[0]), 2)
        
        # Check that the data is in the right positions
        # Monday (index 0) should have data for 2023-01-02
        self.assertIsNotNone(result[0][1])  # Monday of last week
        self.assertEqual(result[0][1]["date"], "2023-01-02")
        self.assertEqual(result[0][1]["guppi"], 3)
        self.assertEqual(result[0][1]["claude"], 0)
        self.assertEqual(result[0][1]["lines"], 3)
        
        # Tuesday (index 1) should have data for 2023-01-03
        self.assertIsNotNone(result[1][1])  # Tuesday of last week
        self.assertEqual(result[1][1]["date"], "2023-01-03")
        self.assertEqual(result[1][1]["guppi"], 0)
        self.assertEqual(result[1][1]["claude"], 7)
        self.assertEqual(result[1][1]["lines"], 7)

    def test_heatmap_levels(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},  # Sunday, 15 lines
            "2023-01-02": {"guppi": 3, "claude": 0},   # Monday, 3 lines
            "2023-01-03": {"guppi": 0, "claude": 7},   # Tuesday, 7 lines
        }
        result = heatmap(daily, "2023-01-03", 2)
        self.assertEqual(result[6][0]["level"], 4)  # Sunday 2023-01-01 is the last row of the first column
        
        # Peak is 15 (Sunday)
        # Monday (3 lines) -> level = 1 + (3 * 4 - 1) // 15 = 1 + 11 // 15 = 1
        # Tuesday (7 lines) -> level = 1 + (7 * 4 - 1) // 15 = 1 + 27 // 15 = 2
        # Sunday (15 lines) -> level = 1 + (15 * 4 - 1) // 15 = 1 + 59 // 15 = 4
        
        # Check that level is calculated correctly
        self.assertEqual(result[0][1]["level"], 1)  # Monday, 3 lines
        self.assertEqual(result[1][1]["level"], 2)  # Tuesday, 7 lines

    def test_heatmap_future_dates(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},
            "2023-01-02": {"guppi": 3, "claude": 0},
        }
        result = heatmap(daily, "2023-01-01", 2)
        
        # All dates after today should be None
        # Since today is 2023-01-01, and we're looking at 2 weeks, 
        # the future dates should be None
        for row in result:
            for cell in row:
                if cell is not None:
                    # All cells should be from or before today
                    self.assertLessEqual(cell["date"], "2023-01-01")

    def test_cards_empty(self):
        result = cards({}, "2023-01-01")
        expected = {
            "total_lines": 0,
            "guppi_lines": 0,
            "claude_lines": 0,
            "guppi_share": 0,
            "active_days": 0,
            "peak_date": None,
            "last_30_lines": 0
        }
        self.assertEqual(result, expected)

    def test_cards_basic(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},
            "2023-01-02": {"guppi": 3, "claude": 0},
            "2023-01-03": {"guppi": 0, "claude": 7},
        }
        result = cards(daily, "2023-01-03")
        expected = {
            "total_lines": 25,
            "guppi_lines": 13,
            "claude_lines": 12,
            "guppi_share": 52,  # (13 * 100 + 25 // 2) // 25 = (1300 + 12) // 25 = 1312 // 25 = 52
            "active_days": 3,
            "peak_date": "2023-01-01",
            "last_30_lines": 25
        }
        self.assertEqual(result, expected)

    def test_cards_guppi_share_rounding(self):
        daily = {
            "2023-01-01": {"guppi": 1, "claude": 1},
        }
        result = cards(daily, "2023-01-01")
        # 1/2 = 0.5, should round up to 1 (half up)
        self.assertEqual(result["guppi_share"], 50)

    def test_cards_guppi_share_zero_total(self):
        daily = {
            "2023-01-01": {"guppi": 0, "claude": 0},
        }
        result = cards(daily, "2023-01-01")
        self.assertEqual(result["guppi_share"], 0)

    def test_cards_active_days(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},
            "2023-01-02": {"guppi": 0, "claude": 0},  # No lines
            "2023-01-03": {"guppi": 0, "claude": 7},
        }
        result = cards(daily, "2023-01-03")
        self.assertEqual(result["active_days"], 2)  # Only 2 days with lines

    def test_cards_peak_date_earliest_on_tie(self):
        daily = {
            "2023-01-01": {"guppi": 10, "claude": 5},  # 15 lines
            "2023-01-02": {"guppi": 10, "claude": 5},  # 15 lines (tie)
            "2023-01-03": {"guppi": 0, "claude": 7},   # 7 lines
        }
        result = cards(daily, "2023-01-03")
        # Should return the earliest date with peak lines (2023-01-01)
        self.assertEqual(result["peak_date"], "2023-01-01")

    def test_cards_peak_date_none_when_no_lines(self):
        daily = {
            "2023-01-01": {"guppi": 0, "claude": 0},
            "2023-01-02": {"guppi": 0, "claude": 0},
        }
        result = cards(daily, "2023-01-02")
        self.assertIsNone(result["peak_date"])

    def test_cards_last_30_lines(self):
        # Create data for 30 days
        daily = {}
        for i in range(30):
            date = datetime.date.fromisoformat("2023-01-01") - datetime.timedelta(days=i)
            date_str = date.isoformat()
            daily[date_str] = {"guppi": 5, "claude": 5}
        
        result = cards(daily, "2023-01-01")
        # Should be 30 days * 10 lines = 300
        self.assertEqual(result["last_30_lines"], 300)

if __name__ == '__main__':
    unittest.main()