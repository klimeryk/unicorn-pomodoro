import time

import config
from compat import ticks_add, ticks_diff

_NTP_HOST = "pool.ntp.org"
_NTP_TIMEOUT_S = 2  # each NTP attempt blocks the main loop for up to this long
_NTP_ATTEMPTS = 3
_NTP_RETRY_MS = 1000
_CONNECT_TIMEOUT_MS = config.WIFI_TIMEOUT_S * 1000
_RESYNC_MS = config.NTP_RESYNC_HOURS * 3600 * 1000

LINK_PENDING = 0
LINK_UP = 1
LINK_FAILED = 2


class _Wifi:
    def __init__(self, ssid, password):
        import network

        self._ssid = ssid
        self._password = password
        # Not every firmware build exports these; fallbacks are CYW43 link statuses.
        self._hard_failures = (
            getattr(network, "STAT_WRONG_PASSWORD", -3),
            getattr(network, "STAT_NO_AP_FOUND", -2),
            getattr(network, "STAT_CONNECT_FAIL", -1),
        )
        if config.WIFI_COUNTRY:
            network.country(config.WIFI_COUNTRY)
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)
        try:  # noqa: SIM105 - contextlib.suppress isn't reliably on-device
            self._wlan.config(pm=getattr(network.WLAN, "PM_NONE", 0xA11140))
        except (OSError, ValueError):
            pass
        time.sleep_ms(500)

    def _online(self):
        return self._wlan.isconnected() and self._wlan.ifconfig()[0] != "0.0.0.0"

    def connect(self):
        # wlan.connect() only starts the join; status() reports the outcome.
        if not self._online():
            self._wlan.disconnect()
            self._wlan.connect(self._ssid, self._password)

    def status(self):
        if self._online():
            return LINK_UP
        if self._wlan.status() in self._hard_failures:
            return LINK_FAILED
        return LINK_PENDING


def _open_wifi():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        return None
    return _Wifi(WIFI_SSID, WIFI_PASSWORD)


def _ntp_settime():
    import ntptime

    ntptime.host = _NTP_HOST
    ntptime.timeout = _NTP_TIMEOUT_S
    try:
        ntptime.settime()
        return True
    except Exception:  # a bad NTP reply must not kill the app
        return False


def _eu_dst_active(utc):
    month = utc[1]
    if month < 3 or month > 10:
        return False
    if 3 < month < 10:
        return True
    day, hour, weekday = utc[2], utc[3], utc[6]
    # The last Sunday of March/October is the 25th-31st; clocks change at
    # 01:00 UTC. weekday: Monday == 0.
    latest_sunday = day - (weekday + 1) % 7
    switched = latest_sunday >= 25 and (latest_sunday < day or hour >= 1)
    return switched if month == 3 else not switched


class NetworkTime:
    def __init__(self):
        self.synced = False
        self._enabled = True
        self._wifi = None
        self._syncing = False
        self._retry_delay_s = config.WIFI_RETRY_START_S
        self._next_sync_at = None
        self._connect_attempts = 0
        self._connect_deadline = 0
        self._ntp_failures = 0
        self._ntp_at = 0

    def poll(self, now):
        # Call only while idle: an NTP attempt can still block for
        # _NTP_TIMEOUT_S. Everything else returns immediately.
        if not self._enabled:
            return
        if not self._syncing:
            if self._next_sync_at is None or ticks_diff(now, self._next_sync_at) >= 0:
                self._begin_sync(now)
            return
        status = self._wifi.status()
        if status == LINK_UP:
            self._try_ntp(now)
        elif status == LINK_FAILED or ticks_diff(now, self._connect_deadline) >= 0:
            if self._connect_attempts < config.WIFI_CONNECT_ATTEMPTS:
                self._start_connect(now)
            else:
                self._finish_sync(now, False)

    def _begin_sync(self, now):
        if self._wifi is None:
            self._wifi = _open_wifi()
            if self._wifi is None:
                self._enabled = False
                return
        self._syncing = True
        self._connect_attempts = 0
        self._ntp_failures = 0
        self._ntp_at = now
        self._start_connect(now)

    def _start_connect(self, now):
        self._connect_attempts += 1
        self._wifi.connect()
        self._connect_deadline = ticks_add(now, _CONNECT_TIMEOUT_MS)

    def _try_ntp(self, now):
        if ticks_diff(now, self._ntp_at) < 0:
            return
        if _ntp_settime():
            self._finish_sync(now, True)
            return
        self._ntp_failures += 1
        if self._ntp_failures >= _NTP_ATTEMPTS:
            self._finish_sync(now, False)
        else:
            self._ntp_at = ticks_add(now, _NTP_RETRY_MS)

    def _finish_sync(self, now, success):
        self._syncing = False
        if success:
            self.synced = True
        if self.synced:
            delay_ms = _RESYNC_MS
        else:
            delay_ms = self._retry_delay_s * 1000
            self._retry_delay_s = min(self._retry_delay_s * 2, config.WIFI_RETRY_MAX_S)
        self._next_sync_at = ticks_add(now, delay_ms)

    def local_hms(self):
        if not self.synced:
            return None
        utc_s = time.time()
        offset_s = int(config.UTC_OFFSET_HOURS * 3600)
        if config.AUTO_DST_EU and _eu_dst_active(time.gmtime(utc_s)):
            offset_s += 3600
        local = time.gmtime(utc_s + offset_s)
        return local[3], local[4], local[5]
