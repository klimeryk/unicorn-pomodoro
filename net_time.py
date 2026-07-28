import time

import config

synced = False


def _connect(wlan, network, ssid, password):
    got_ip = getattr(network, "STAT_GOT_IP", 3)
    hard_fail = (
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
            if status == got_ip and wlan.ifconfig()[0] != "0.0.0.0":
                return True
            if status in hard_fail:
                break
            time.sleep_ms(100)
        if wlan.isconnected() and wlan.ifconfig()[0] != "0.0.0.0":
            return True
    return False


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
    try:  # noqa: SIM105 - contextlib.suppress isn't reliably on-device
        wlan.config(pm=getattr(network.WLAN, "PM_NONE", 0xA11140))
    except (OSError, ValueError):
        pass
    time.sleep_ms(500)
    connected = wlan.isconnected() and wlan.ifconfig()[0] != "0.0.0.0"
    if not connected and not _connect(wlan, network, WIFI_SSID, WIFI_PASSWORD):
        return False

    ntptime.host = "pool.ntp.org"
    ntptime.timeout = 5
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
