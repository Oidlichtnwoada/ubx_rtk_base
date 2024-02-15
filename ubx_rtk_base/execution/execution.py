import time

from ubx_rtk_base.utils.ubx_utils import UbloxGnssReceiver


def start_receiver() -> None:
    ublox_gnss_receiver = UbloxGnssReceiver()
    ublox_gnss_receiver.start()
    ublox_gnss_receiver.do_factory_reset()
    ublox_gnss_receiver.configure_rtcm3()
    time.sleep(10)
    ublox_gnss_receiver.stop()
