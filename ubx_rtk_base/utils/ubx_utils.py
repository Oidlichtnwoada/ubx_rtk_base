import dataclasses
import datetime
import io
import queue
import re
import threading
import time
import typing

import pynmeagps
import pyrtcm
import pyubx2
import serial
import serial.tools.list_ports
import serial.tools.list_ports_common

from ubx_rtk_base.utils.math_utils import value_to_precision_integers
from ubx_rtk_base.utils.string_utils import get_default_string_value

Message = typing.Union[pyubx2.UBXMessage, pynmeagps.NMEAMessage, pyrtcm.RTCMMessage]
MessageCallback = typing.Callable[[Message], None]


@dataclasses.dataclass(frozen=True, order=True, kw_only=True)
class Position:
    latitude_degrees: float
    longitude_degrees: float
    altitude_meters: float


def is_ublox_gnss_receiver(
    port_info: serial.tools.list_ports_common.ListPortInfo,
) -> bool:
    manufacturer = get_default_string_value(port_info.manufacturer)
    product = get_default_string_value(port_info.product)
    description = get_default_string_value(port_info.description)
    return (
        manufacturer == "u-blox AG - www.u-blox.com"
        and product == "u-blox GNSS receiver"
        and description == "u-blox GNSS receiver"
    )


def get_ports_of_ublox_gnss_receiver() -> tuple[str, ...]:
    port_list = serial.tools.list_ports.comports(include_links=True)
    gnss_receiver_port_list = filter(is_ublox_gnss_receiver, port_list)
    return tuple([x.device for x in gnss_receiver_port_list])


def get_test_position() -> Position:
    return Position(
        latitude_degrees=48.6467596667,
        longitude_degrees=16.791555,
        altitude_meters=215.3,
    )


def get_default_ublox_gnss_receiver_baudrate() -> int:
    return 9600


def get_default_ublox_gnss_receiver_timeout() -> float:
    return 0.1


def get_default_ublox_gnss_receiver_port_type() -> str:
    return "USB"


def get_default_accuracy_limit_millimeters() -> int:
    return 50000


def get_default_survey_in_min_duration_seconds() -> int:
    return 60


def get_internal_accuracy_limit_value(accuracy_limit_millimeters: int) -> int:
    return accuracy_limit_millimeters * 10


def get_ublox_gnss_receiver_serial() -> serial.Serial:
    ublox_gnss_receiver_ports = get_ports_of_ublox_gnss_receiver()
    if len(ublox_gnss_receiver_ports) == 0:
        raise RuntimeError
    return serial.Serial(
        port=ublox_gnss_receiver_ports[0],
        baudrate=get_default_ublox_gnss_receiver_baudrate(),
        timeout=get_default_ublox_gnss_receiver_timeout(),
    )


def is_ack_message_correct(
    ack_message: pyubx2.UBXMessage, sent_message: pyubx2.UBXMessage
) -> bool:
    sent_message_identity: str = sent_message.identity
    ack_message_string = str(ack_message)
    match = re.search("msgID=([A-Z]+-[A-Z]+)", ack_message_string)
    if match is None:
        raise RuntimeError
    try:
        ack_message_identity = match.group(1)
        return sent_message_identity == ack_message_identity
    except IndexError:
        raise RuntimeError


def send_message_to_ublox_gnss_receiver(
    serial_port: serial.Serial,
    message: pyubx2.UBXMessage,
    ack_queue: queue.Queue[pyubx2.UBXMessage],
) -> None:
    serial_port.write(message.serialize())
    ack_message = ack_queue.get()
    if not is_ack_message_correct(ack_message, message):
        raise RuntimeError


def get_default_message_callback_for_ublox_gnss_receiver(
    message: Message,
) -> None:
    print(
        f"following message received on {datetime.datetime.now(tz=datetime.UTC)}: {str(message)}"
    )


def is_message_ublox_acknowledge(
    message: Message,
) -> bool:
    if isinstance(message, pyubx2.UBXMessage):
        return message.identity in ("ACK-ACK", "ACK-NAK")
    else:
        return False


def read_messages_from_ublox_gnss_receiver(
    serial_port: serial.Serial,
    running_queue: queue.Queue[bool],
    ack_queue: queue.Queue[pyubx2.UBXMessage],
    callback: MessageCallback = get_default_message_callback_for_ublox_gnss_receiver,
) -> None:
    ublox_reader = pyubx2.UBXReader(
        io.BufferedReader(serial_port),
        protfilter=pyubx2.UBX_PROTOCOL | pyubx2.NMEA_PROTOCOL | pyubx2.RTCM3_PROTOCOL,
        quitonerror=pyubx2.ERR_RAISE,
    )
    while not running_queue.empty():
        if serial_port.in_waiting:
            _, parsed_data = ublox_reader.read()
            if parsed_data:
                if is_message_ublox_acknowledge(parsed_data):
                    ack_queue.put(parsed_data)
                else:
                    callback(parsed_data)


def get_factory_reset_message_for_ublox_gnss_receiver() -> pyubx2.UBXMessage:
    return pyubx2.UBXMessage(
        "CFG",
        "CFG-CFG",
        pyubx2.SET,
        clearMask=b"\x1f\x1f\x00\x00",
        loadMask=b"\x1f\x1f\x00\x00",
        devBBR=1,
        devFlash=1,
        devEEPROM=1,
    )


def get_configuration_ublox_message(
    cfg_data: tuple[tuple[str, int], ...]
) -> pyubx2.UBXMessage:
    layers = 7
    transaction = 0
    ubx_msg = pyubx2.UBXMessage.config_set(layers, transaction, list(cfg_data))
    if isinstance(ubx_msg, pyubx2.UBXMessage):
        return ubx_msg
    else:
        raise RuntimeError


def get_rtcm3_base_station_outputs_for_ublox_gnss_receiver() -> pyubx2.UBXMessage:
    cfg_data: tuple[tuple[str, int], ...] = ()
    for rtcm_type in (
        "1005",
        "1077",
        "1087",
        "1097",
        "1127",
        "1230",
    ):
        cfg_data += (
            (
                f"CFG_MSGOUT_RTCM_3X_TYPE{rtcm_type}_{get_default_ublox_gnss_receiver_port_type()}",
                1,
            ),
        )
    return get_configuration_ublox_message(cfg_data)


def get_survey_in_mode_for_ublox_gnss_receiver(
    accuracy_limit_millimeters: int = get_default_accuracy_limit_millimeters(),
    survey_in_min_duration_seconds: int = get_default_survey_in_min_duration_seconds(),
) -> pyubx2.UBXMessage:
    cfg_data = (
        ("CFG_TMODE_MODE", 1),
        (
            "CFG_TMODE_SVIN_ACC_LIMIT",
            get_internal_accuracy_limit_value(accuracy_limit_millimeters),
        ),
        ("CFG_TMODE_SVIN_MIN_DUR", survey_in_min_duration_seconds),
        (f"CFG_MSGOUT_UBX_NAV_SVIN_{get_default_ublox_gnss_receiver_port_type()}", 1),
    )
    return get_configuration_ublox_message(cfg_data)


def get_fixed_mode_for_ublox_gnss_receiver(
    position: Position,
    accuracy_limit_millimeters: int = get_default_accuracy_limit_millimeters(),
) -> pyubx2.UBXMessage:
    altitude_first_part, altitude_second_part = value_to_precision_integers(
        position.altitude_meters, scale_factor=10**2, decimal_places=1
    )
    latitude_first_part, latitude_second_part = value_to_precision_integers(
        position.latitude_degrees
    )
    longitude_first_part, longitude_second_part = value_to_precision_integers(
        position.longitude_degrees
    )
    cfg_data = (
        ("CFG_TMODE_MODE", 2),
        ("CFG_TMODE_POS_TYPE", 1),
        (
            "CFG_TMODE_FIXED_POS_ACC",
            get_internal_accuracy_limit_value(accuracy_limit_millimeters),
        ),
        ("CFG_TMODE_HEIGHT", altitude_first_part),
        ("CFG_TMODE_HEIGHT_HP", altitude_second_part),
        ("CFG_TMODE_LAT", latitude_first_part),
        ("CFG_TMODE_LAT_HP", latitude_second_part),
        ("CFG_TMODE_LON", longitude_first_part),
        ("CFG_TMODE_LON_HP", longitude_second_part),
    )
    return get_configuration_ublox_message(cfg_data)


class UbloxGnssReceiver:
    def __init__(
        self,
        callback: MessageCallback = get_default_message_callback_for_ublox_gnss_receiver,
    ) -> None:
        self.serial = get_ublox_gnss_receiver_serial()
        self.callback = callback
        self.ack_queue: queue.Queue[pyubx2.UBXMessage] = queue.Queue()
        self.running_queue: queue.Queue[bool] = queue.Queue()
        self.read_messages_thread = threading.Thread(target=self.read_messages)

    def start(self) -> None:
        self.running_queue.put(True)
        self.read_messages_thread.start()

    def stop(self) -> None:
        self.running_queue.get()
        self.read_messages_thread.join()

    def do_factory_reset(self) -> None:
        self.send_message(get_factory_reset_message_for_ublox_gnss_receiver())

    def configure_rtcm3(self) -> None:
        self.send_message(get_rtcm3_base_station_outputs_for_ublox_gnss_receiver())

    def configure_survey_in_mode(self) -> None:
        self.send_message(get_survey_in_mode_for_ublox_gnss_receiver())

    def configure_fixed_mode(self, position: Position) -> None:
        self.send_message(get_fixed_mode_for_ublox_gnss_receiver(position))

    def read_messages(self) -> None:
        read_messages_from_ublox_gnss_receiver(
            self.serial, self.running_queue, self.ack_queue, self.callback
        )

    def send_message(self, message: pyubx2.UBXMessage) -> None:
        send_message_to_ublox_gnss_receiver(self.serial, message, self.ack_queue)

    def wait_until_terminated(self) -> None:
        while not self.running_queue.empty():
            time.sleep(0.1)
