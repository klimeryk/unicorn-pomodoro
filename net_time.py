import time

import config
from compat import ticks_add, ticks_diff

_NTP_HOST = "pool.ntp.org"
_NTP_TIMEOUT_S = 5
_NTP_ATTEMPTS = 3
_RESYNC_MS = config.NTP_RESYNC_HOURS * 3600 * 1000


def _is_online(wlan):
    return wlan.isconnected() and wlan.ifconfig()[0] != "0.0.0.0"


def _connect(wlan, network, ssid, password):
    # Not every firmware build exports these; fallbacks are CYW43 link statuses.
    got_ip = getattr(network, "STAT_GOT_IP", 3)
    hard_failures = (
        getattr(network, "STAT_WRONG_PASSWORD", -3),
        getattr(network, "STAT_NO_AP_FOUND", -2),
        getattr(network, "STAT_CONNECT_FAIL", -1),
    )
    for attempt in range(config.WIFI_CONNECT_ATTEMPTS):
        if attempt:
            wlan.disconnect()
            time.sleep_ms(500)
        wlan.connect(ssid, password)
        deadline = time.ticks_add(time.ticks_ms(), config.WIFI_TIMEOUT_S * 1000)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            status = wlan.status()
            if status == got_ip and _is_online(wlan):
                return True
            if status in hard_failures:
                break
            time.sleep_ms(100)
        if _is_online(wlan):
            return True
    return False


def _sync_rtc():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        return False
    import network
    import ntptime

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:  # noqa: SIM105 - contextlib.suppress isn't reliably on-device
        wlan.config(pm=getattr(network.WLAN, "PM_NONE", 0xA11140))
    except (OSError, ValueError):
        pass
    time.sleep_ms(500)
    if not _is_online(wlan) and not _connect(wlan, network, WIFI_SSID, WIFI_PASSWORD):
        return False

    ntptime.host = _NTP_HOST
    ntptime.timeout = _NTP_TIMEOUT_S
    for _ in range(_NTP_ATTEMPTS):
        try:
            ntptime.settime()
            return True
        except OSError:
            time.sleep(1)
    return False


def _last_sunday(year, month):
    # Only valid for 31-day months (March and October).
    weekday = time.localtime(time.mktime((year, month, 31, 12, 0, 0, 0, 0)))[6]
    return 31 - (weekday + 1) % 7


def _eu_dst_active(utc_s):
    year = time.localtime(utc_s)[0]
    start = time.mktime((year, 3, _last_sunday(year, 3), 1, 0, 0, 0, 0))
    end = time.mktime((year, 10, _last_sunday(year, 10), 1, 0, 0, 0, 0))
    return start <= utc_s < end


class NetworkTime:
    def __init__(self):
        self.synced = False
        self._retry_delay_s = config.WIFI_RETRY_START_S
        self._next_sync_at = 0

    def sync(self, now):
        if _sync_rtc():
            self.synced = True
        if self.synced:
            delay_ms = _RESYNC_MS
        else:
            delay_ms = self._retry_delay_s * 1000
            self._retry_delay_s = min(self._retry_delay_s * 2, config.WIFI_RETRY_MAX_S)
        self._next_sync_at = ticks_add(now, delay_ms)

    def sync_if_due(self, now):
        if ticks_diff(now, self._next_sync_at) >= 0:
            self.sync(now)

    def local_hms(self):
        if not self.synced:
            return None
        utc_s = time.time()
        offset_s = config.UTC_OFFSET_HOURS * 3600
        if config.AUTO_DST_EU and _eu_dst_active(utc_s):
            offset_s += 3600
        local = time.localtime(utc_s + offset_s)
        return local[3], local[4], local[5]
