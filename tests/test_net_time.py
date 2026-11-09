import unittest
from unittest import mock

import config
import net_time
from net_time import NetworkTime

RETRY_START_MS = config.WIFI_RETRY_START_S * 1000
RETRY_MAX_MS = config.WIFI_RETRY_MAX_S * 1000
RESYNC_MS = config.NTP_RESYNC_HOURS * 3600 * 1000


class NetworkTimeScheduleTest(unittest.TestCase):
    def setUp(self):
        self.sync_results = []
        self.sync_attempts = 0
        patcher = mock.patch.object(net_time, "_sync_rtc", self._fake_sync_rtc)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.network_time = NetworkTime()

    def _fake_sync_rtc(self):
        self.sync_attempts += 1
        return self.sync_results.pop(0)

    def _assert_next_attempt_after(self, now, delay_ms):
        attempts = self.sync_attempts
        self.network_time.sync_if_due(now + delay_ms - 1)
        self.assertEqual(self.sync_attempts, attempts, "synced too early")
        self.network_time.sync_if_due(now + delay_ms)
        self.assertEqual(self.sync_attempts, attempts + 1, "did not sync when due")
        return now + delay_ms

    def test_unsynced_retries_back_off_up_to_the_ceiling(self):
        self.sync_results = [False] * 8
        self.network_time.sync(0)
        now = 0
        expected_delay_ms = RETRY_START_MS
        while self.sync_results:
            now = self._assert_next_attempt_after(now, expected_delay_ms)
            expected_delay_ms = min(expected_delay_ms * 2, RETRY_MAX_MS)
        self.assertEqual(expected_delay_ms, RETRY_MAX_MS)
        self.assertFalse(self.network_time.synced)

    def test_success_switches_to_periodic_resync(self):
        self.sync_results = [False, True, False, False]
        self.network_time.sync(0)
        now = self._assert_next_attempt_after(0, RETRY_START_MS)
        self.assertTrue(self.network_time.synced)
        now = self._assert_next_attempt_after(now, RESYNC_MS)
        self.assertTrue(self.network_time.synced)
        self._assert_next_attempt_after(now, RESYNC_MS)

    def test_time_is_unknown_until_synced(self):
        self.assertIsNone(self.network_time.local_hms())
