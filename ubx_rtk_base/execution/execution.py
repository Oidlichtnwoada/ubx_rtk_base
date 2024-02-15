import functools
import signal
import types
import typing

from ubx_rtk_base.utils.ubx_utils import UbloxGnssReceiver


def receiver_stop_signal_handler(
    signum: int, frame: typing.Optional[types.FrameType], receiver: UbloxGnssReceiver
) -> None:
    receiver.stop()


def start_receiver() -> None:
    ublox_gnss_receiver = UbloxGnssReceiver()
    ublox_gnss_receiver.start()
    ublox_gnss_receiver.do_factory_reset()
    ublox_gnss_receiver.configure_rtcm3()
    ublox_gnss_receiver.configure_survey_in_mode()
    handler = functools.partial(
        receiver_stop_signal_handler, receiver=ublox_gnss_receiver
    )
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    ublox_gnss_receiver.wait_until_terminated()
