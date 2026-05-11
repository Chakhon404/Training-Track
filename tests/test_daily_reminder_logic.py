
import unittest
from unittest.mock import MagicMock, patch
from daily_reminder import get_daily_status
import datetime
import pytz

class TestDailyReminder(unittest.TestCase):

    @patch('daily_reminder.datetime')
    def test_get_daily_status_logic(self, mock_datetime):
        # Setup mocks
        mock_supabase = MagicMock()
        
        # Mock today's date
        tz_bkk = pytz.timezone('Asia/Bangkok')
        fixed_now = datetime.datetime(2023, 10, 27, 12, 0, 0, tzinfo=tz_bkk)
        mock_datetime.now.return_value = fixed_now
        today = fixed_now.strftime("%Y-%m-%d")

        # Mock profile response
        mock_profile = {
            "default_supplements": ["creatine", "omega_3"],
            "updated_at": "2023-10-27T10:00:00Z"
        }
        mock_supabase.table().select().order().limit().maybe_single().execute.return_value.data = mock_profile

        # Mock nutrition response
        # Entry 1: Creatine taken
        # Entry 2: Macros
        mock_nutrition_data = [
            {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 10, "creatine": True, "omega3": False},
            {"calories": 300, "protein_g": 20, "carbs_g": 40, "fat_g": 5, "creatine": False, "omega3": False}
        ]
        mock_supabase.table().select().gte().lte().execute.return_value.data = mock_nutrition_data

        # Run function
        profile, stats = get_daily_status(supabase_client=mock_supabase)

        # Assertions
        self.assertEqual(profile, mock_profile)
        self.assertEqual(stats["calories"], 800)
        self.assertEqual(stats["protein_g"], 50)
        self.assertEqual(stats["carbs_g"], 90)
        self.assertEqual(stats["fat_g"], 15)
        
        # Supplements check
        # Creatine should be in taken_sups because one entry has creatine=True
        # Omega_3 should NOT be in taken_sups because no entry has omega3=True
        # missing_supplements should contain 'omega_3'
        self.assertIn("omega_3", stats["missing_supplements"])
        self.assertNotIn("creatine", stats["missing_supplements"])

if __name__ == '__main__':
    unittest.main()
