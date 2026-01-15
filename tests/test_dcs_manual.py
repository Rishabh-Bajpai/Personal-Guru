import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from app.core.extensions import db
from app.core.models import Installation, Topic, SyncLog
from app.common.dcs import DCSClient

class TestDCS(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.common.dcs.requests.post')
    @patch('app.common.utils.get_system_info')
    def test_registration(self, mock_sys_info, mock_post):
        # Setup mocks
        mock_sys_info.return_value = {
            'cpu_cores': 4, 'ram_gb': 16, 'gpu_model': 'TestGPU',
            'os_version': 'TestOS', 'install_method': 'test'
        }

        # Mock Register Response
        mock_reg_resp = MagicMock()
        mock_reg_resp.status_code = 201
        mock_reg_resp.json.return_value = {"installation_id": "test-uuid-1234"}

        # Mock Update Response
        mock_update_resp = MagicMock()
        mock_update_resp.status_code = 200
        mock_update_resp.json.return_value = {"status": "updated"}

        mock_post.side_effect = [mock_reg_resp, mock_update_resp]

        client = DCSClient()
        success = client.register_device()

        self.assertTrue(success)
        self.assertEqual(client.installation_id, "test-uuid-1234")

        # Verify DB
        inst = Installation.query.first()
        self.assertIsNotNone(inst)
        self.assertEqual(inst.installation_id, "test-uuid-1234")

    @patch('app.common.dcs.requests.post')
    def test_sync(self, mock_post):
        # Pre-seed installation
        inst = Installation(installation_id="test-uuid-sync", install_method="test")
        db.session.add(inst)

        # Add some data
        topic = Topic(name="Test Topic", user_id="test_user", sync_status="pending")
        db.session.add(topic)

        # Add new tables
        from app.core.models import Feedback, AIModelPerformance
        fb = Feedback(user_id="test_user", feedback_type="in_place", comment="Great!", sync_status="pending")
        db.session.add(fb)

        perf = AIModelPerformance(user_id="test_user", model_type="LLM", latency_ms=100, sync_status="pending")
        db.session.add(perf)

        db.session.commit()

        # Mock Sync Response
        mock_sync_resp = MagicMock()
        mock_sync_resp.status_code = 200

        mock_post.return_value = mock_sync_resp

        client = DCSClient()
        client.sync_data() # This should find the pre-seeded ID

        # Verify Sync Status
        t = Topic.query.first()
        self.assertEqual(t.sync_status, 'synced')

        fb_query = Feedback.query.first()
        self.assertEqual(fb_query.sync_status, 'synced')

        perf_query = AIModelPerformance.query.first()
        self.assertEqual(perf_query.sync_status, 'synced')

        # Verify SyncLog
        log = SyncLog.query.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'success')

if __name__ == '__main__':
    unittest.main()
