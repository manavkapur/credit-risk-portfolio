import os
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_views_filters_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ['REVIEW_DB_PATH'] = str(Path(tmp)/'reviews.db')
            try:
                app = AppTest.from_file('app/app.py').run(timeout=30)
                self.assertFalse(app.exception)
                app.radio(key='active_view').set_value('Anomaly review').run(timeout=30)
                app.button[0].click().run(timeout=30)
                self.assertFalse(app.exception)
                from src.reviews import read_reviews
                self.assertEqual(len(read_reviews()),1)
                self.assertEqual(app.radio(key='active_view').value,'Anomaly review')
                app.sidebar.multiselect[0].set_value([]).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.warning)
            finally:
                os.environ.pop('REVIEW_DB_PATH',None)
