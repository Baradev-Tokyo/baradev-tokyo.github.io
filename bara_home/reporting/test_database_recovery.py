from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .database_recovery import RecoveryError, SupabaseProject, ensure_database_ready


class SupabaseRecoveryTests(SimpleTestCase):
    def setUp(self):
        self.connection = MagicMock(settings_dict={})
        self.project = MagicMock()
        self.wait = MagicMock()

    @patch("reporting.database_recovery.probe_database", return_value=True)
    def test_running_database_does_not_call_management_api(self, probe):
        self.assertFalse(ensure_database_ready(self.connection, self.project, wait=self.wait))
        probe.assert_called_once()
        self.project.status.assert_not_called()
        self.project.resume.assert_not_called()

    @patch("reporting.database_recovery.probe_database", side_effect=[False, False, True])
    def test_confirmed_pause_resumes_and_waits_for_sql(self, probe):
        self.project.status.return_value = "INACTIVE"
        self.assertTrue(ensure_database_ready(
            self.connection, self.project, auto_resume=True, wait=self.wait,
        ))
        self.project.resume.assert_called_once()
        self.assertEqual(probe.call_count, 3)

    @patch("reporting.database_recovery.probe_database", return_value=False)
    def test_paused_project_requires_opt_in(self, probe):
        self.project.status.return_value = "INACTIVE"
        with self.assertRaisesRegex(RecoveryError, "paused"):
            ensure_database_ready(self.connection, self.project, wait=self.wait)
        self.project.resume.assert_not_called()

    @patch("reporting.database_recovery.probe_database", return_value=False)
    def test_other_errors_never_trigger_restore(self, probe):
        for status in ("ACTIVE_UNHEALTHY", "RESTORING", "RESTORE_FAILED"):
            with self.subTest(status=status):
                self.project.status.return_value = status
                with self.assertRaises(RecoveryError):
                    ensure_database_ready(self.connection, self.project, auto_resume=True, wait=self.wait)
        self.project.resume.assert_not_called()

    def test_only_matching_direct_or_session_pooler_project(self):
        ref = "abcdefghijklmnopqrst"
        project = SupabaseProject(ref, "fixture")
        self.assertTrue(project.matches_database({"HOST": f"db.{ref}.supabase.co"}))
        self.assertTrue(project.matches_database({
            "HOST": "aws-0-ap-northeast-1.pooler.supabase.com", "USER": f"reporter.{ref}",
        }))
        self.assertFalse(project.matches_database({
            "HOST": "aws-0-ap-northeast-1.pooler.supabase.com", "USER": "reporter.other",
        }))
        self.assertFalse(project.matches_database({"HOST": f"db.{ref}.supabase.co.example.com"}))
