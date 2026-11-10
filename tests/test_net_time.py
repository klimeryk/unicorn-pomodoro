import calendar
import time
import unittest
from unittest import mock

import config
import net_time
from compat import ticks_add
from net_time import LINK_FAILED, LINK_PENDING, LINK_UP, NetworkTime

CONNECT_TIMEOUT_MS = config.WIFI_TIMEOUT_S * 1000
RETRY_START_MS = config.WIFI_RETRY_START_S * 1000
RETRY_MAX_MS = config.WIFI_RETRY_MAX_S * 1000
RESYNC_MS = config.NTP_RESYNC_HOURS * 3600 * 1000


class FakeWifi:
    def __init__(self):
        self.link = LINK_PENDING
        self.connects = 0

    def connect(self):
        self.connects += 1

    def status(self):
        return self.link


class NetworkTimeTestCase(unittest.TestCase):
    def setUp(self):
        self.wifi = FakeWifi()
        self.wifi_opens = 0
        self.ntp_results = []
        self.ntp_attempts = 0
        for name, fake in (
            ("_open_wifi", self._fake_open_wifi),
            ("_ntp_settime", self._fake_ntp_settime),
        ):
            patcher = mock.patch.object(net_time, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.network_time = NetworkTime()

    def _fake_open_wifi(self):
        self.wifi_opens += 1
        return self.wifi

    def _fake_ntp_settime(self):
        self.ntp_attempts += 1
        return self.ntp_results.pop(0)

    def _fail_sync(self, start):
        # Times out every connect attempt; returns when the sync gave up.
        now = start
        self.network_time.poll(now)
        for _ in range(config.WIFI_CONNECT_ATTEMPTS):
            now = ticks_add(now, CONNECT_TIMEOUT_MS)
            self.network_time.poll(now)
        return now

    def _sync(self, start):
        # Connects, then syncs on the next poll; returns when it synced.
        self.wifi.link = LINK_UP
        self.ntp_results = [True]
        self.network_time.poll(start)
        now = ticks_add(start, 1)
        self.network_time.poll(now)
        self.wifi.link = LINK_PENDING
        return now

    def _assert_next_sync_after(self, now, delay_ms):
        connects = self.wifi.connects
        self.network_time.poll(ticks_add(now, delay_ms - 1))
        self.assertEqual(self.wifi.connects, connects, "synced too early")
        self.network_time.poll(ticks_add(now, delay_ms))
        self.assertEqual(self.wifi.connects, connects + 1, "did not sync when due")
        return ticks_add(now, delay_ms)


class NetworkTimeScheduleTest(NetworkTimeTestCase):
    def test_first_poll_connects_and_syncs_once_online(self):
        self.network_time.poll(0)
        self.assertEqual(self.wifi.connects, 1)
        self.network_time.poll(100)
        self.assertEqual(self.ntp_attempts, 0)
        self.assertFalse(self.network_time.synced)
        self.wifi.link = LINK_UP
        self.ntp_results = [True]
        self.network_time.poll(200)
        self.assertTrue(self.network_time.synced)
        self.wifi.link = LINK_PENDING
        self._assert_next_sync_after(200, RESYNC_MS)

    def test_missing_secrets_never_retries(self):
        with mock.patch.object(net_time, "_open_wifi", return_value=None) as open_:
            for now in range(0, 10 * RETRY_MAX_MS, RETRY_START_MS):
                self.network_time.poll(now)
        open_.assert_called_once()
        self.assertIsNone(self.network_time.local_hms())

    def test_connect_timeouts_retry_then_back_off_from_the_end(self):
        self.network_time.poll(0)
        for attempt in range(2, config.WIFI_CONNECT_ATTEMPTS + 1):
            deadline = (attempt - 1) * CONNECT_TIMEOUT_MS
            self.network_time.poll(deadline - 1)
            self.assertEqual(self.wifi.connects, attempt - 1)
            self.network_time.poll(deadline)
            self.assertEqual(self.wifi.connects, attempt)
        gave_up = config.WIFI_CONNECT_ATTEMPTS * CONNECT_TIMEOUT_MS
        self.network_time.poll(gave_up)
        self.assertEqual(self.wifi.connects, config.WIFI_CONNECT_ATTEMPTS)
        self._assert_next_sync_after(gave_up, RETRY_START_MS)

    def test_hard_failure_retries_without_waiting_for_the_timeout(self):
        self.wifi.link = LINK_FAILED
        for now in range(config.WIFI_CONNECT_ATTEMPTS + 1):
            self.network_time.poll(now)
        self.assertEqual(self.wifi.connects, config.WIFI_CONNECT_ATTEMPTS)
        self._assert_next_sync_after(config.WIFI_CONNECT_ATTEMPTS, RETRY_START_MS)

    def test_unsynced_retries_back_off_up_to_the_ceiling(self):
        now = self._fail_sync(0)
        expected_delay_ms = RETRY_START_MS
        for _ in range(8):
            now = self._fail_sync(ticks_add(now, expected_delay_ms))
            expected_delay_ms = min(expected_delay_ms * 2, RETRY_MAX_MS)
        self.assertEqual(expected_delay_ms, RETRY_MAX_MS)
        self._assert_next_sync_after(now, RETRY_MAX_MS)
        self.assertFalse(self.network_time.synced)

    def test_ntp_is_retried_once_per_gap_then_backs_off(self):
        self.wifi.link = LINK_UP
        self.ntp_results = [False] * net_time._NTP_ATTEMPTS
        self.network_time.poll(0)
        self.network_time.poll(1)
        self.assertEqual(self.ntp_attempts, 1)
        self.network_time.poll(net_time._NTP_RETRY_MS)
        self.assertEqual(self.ntp_attempts, 1)
        now = 1
        for attempt in range(2, net_time._NTP_ATTEMPTS + 1):
            now += net_time._NTP_RETRY_MS
            self.network_time.poll(now)
            self.assertEqual(self.ntp_attempts, attempt)
        self.assertFalse(self.network_time.synced)
        self.wifi.link = LINK_PENDING
        self._assert_next_sync_after(now, RETRY_START_MS)

    def test_failed_resync_keeps_time_and_waits_full_interval(self):
        now = self._sync(0)
        self.assertTrue(self.network_time.synced)
        now = self._fail_sync(ticks_add(now, RESYNC_MS))
        self.assertTrue(self.network_time.synced)
        self._assert_next_sync_after(now, RESYNC_MS)

    def test_schedule_survives_ticks_wraparound(self):
        start = (1 << 30) - 5000
        now = self._sync(start)
        self.assertTrue(self.network_time.synced)
        self._assert_next_sync_after(now, RESYNC_MS)


def utc(*fields):
    return time.gmtime(calendar.timegm((*fields, 0, 0, 0)))


class EuDstTest(unittest.TestCase):
    def assertDst(self, expected, *fields):
        self.assertEqual(net_time._eu_dst_active(utc(*fields)), expected, fields)

    def test_winter_and_summer(self):
        self.assertDst(False, 2026, 1, 15, 12, 0, 0)
        self.assertDst(False, 2026, 11, 1, 12, 0, 0)
        self.assertDst(False, 2026, 12, 31, 23, 59, 59)
        self.assertDst(True, 2026, 4, 1, 0, 0, 0)
        self.assertDst(True, 2026, 7, 15, 12, 0, 0)
        self.assertDst(True, 2026, 9, 30, 23, 59, 59)

    def test_switches_at_one_utc_on_the_last_sunday_of_march(self):
        self.assertDst(False, 2026, 3, 22, 12, 0, 0)  # an earlier Sunday
        self.assertDst(False, 2026, 3, 28, 23, 59, 59)
        self.assertDst(False, 2026, 3, 29, 0, 59, 59)
        self.assertDst(True, 2026, 3, 29, 1, 0, 0)
        self.assertDst(True, 2026, 3, 31, 0, 0, 0)
        self.assertDst(False, 2027, 3, 28, 0, 59, 59)
        self.assertDst(True, 2027, 3, 28, 1, 0, 0)

    def test_switches_at_one_utc_on_the_last_sunday_of_october(self):
        self.assertDst(True, 2026, 10, 18, 12, 0, 0)  # an earlier Sunday
        self.assertDst(True, 2026, 10, 25, 0, 59, 59)
        self.assertDst(False, 2026, 10, 25, 1, 0, 0)
        self.assertDst(False, 2026, 10, 31, 12, 0, 0)
        self.assertDst(True, 2020, 10, 25, 0, 59, 59)
        self.assertDst(False, 2020, 10, 25, 1, 0, 0)

    def test_last_sunday_on_the_31st(self):
        self.assertDst(False, 2024, 3, 31, 0, 59, 59)
        self.assertDst(True, 2024, 3, 31, 1, 0, 0)
        self.assertDst(False, 2024, 3, 30, 23, 0, 0)
        self.assertDst(True, 2021, 10, 31, 0, 59, 59)
        self.assertDst(False, 2021, 10, 31, 1, 0, 0)


class LocalTimeTest(NetworkTimeTestCase):
    def _local_hms_at(self, *fields, offset_hours=1, dst=True):
        self._sync(0)
        utc_s = calendar.timegm((*fields, 0, 0, 0))
        settings = {"UTC_OFFSET_HOURS": offset_hours, "AUTO_DST_EU": dst}
        clock = mock.patch.object(net_time.time, "time", return_value=utc_s)
        with mock.patch.multiple(config, **settings), clock:
            return self.network_time.local_hms()

    def test_time_is_unknown_until_synced(self):
        self.assertIsNone(self.network_time.local_hms())

    def test_applies_offset_and_dst(self):
        self.assertEqual(self._local_hms_at(2026, 1, 1, 23, 30, 5), (0, 30, 5))
        self.assertEqual(self._local_hms_at(2026, 7, 1, 12, 0, 0), (14, 0, 0))
        self.assertEqual(
            self._local_hms_at(2026, 7, 1, 12, 0, 0, dst=False), (13, 0, 0)
        )

    def test_fractional_offset(self):
        self.assertEqual(
            self._local_hms_at(2026, 1, 1, 0, 0, 0, offset_hours=5.5, dst=False),
            (5, 30, 0),
        )
