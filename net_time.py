# WiFi + NTP time. The Pico W has no battery-backed RTC, so we sync over
# WiFi at boot (credentials in secrets.py).

import time

import config

synced = False


def sync():
    global synced
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        return False
    import network
    import ntptime

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        deadline = time.ticks_add(time.ticks_ms(), config.WIFI_TIMEOUT_S * 1000)
        while not wlan.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            time.sleep_ms(100)
    if not wlan.isconnected():
        return False
    for _ in range(3):
        try:
            ntptime.settime()
            synced = True
            return True
        except OSError:
            time.sleep(1)
    return False


def resync():
    global synced
    try:
        import network
        import ntptime

        if network.WLAN(network.STA_IF).isconnected():
            ntptime.settime()
            synced = True
    except OSError:
        pass


def _last_sunday(year, month):
    weekday = time.localtime(time.mktime((year, month, 31, 12, 0, 0, 0, 0)))[6]
    return 31 - ((weekday + 1) % 7)


def _eu_dst_active(t):
    year = time.localtime(t)[0]
    start = time.mktime((year, 3, _last_sunday(year, 3), 1, 0, 0, 0, 0))
    end = time.mktime((year, 10, _last_sunday(year, 10), 1, 0, 0, 0, 0))
    return start <= t < end


def local_hms():
    if not synced:
        return None
    t = time.time()
    offset = config.UTC_OFFSET_HOURS * 3600
    if config.AUTO_DST_EU and _eu_dst_active(t):
        offset += 3600
    local = time.localtime(t + offset)
    return local[3], local[4], local[5]
