import queue
import re
from io import BufferedReader
from threading import Thread
from typing import Callable

from pynmeagps import NMEAMessage
from pyubx2 import UBXMessage, UBXReader, SET
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo

from ubx_rtk_base.utils.string_utils import get_default_string_value


def is_ublox_gnss_receiver(port_info: ListPortInfo) -> bool:
    manufacturer = get_default_string_value(port_info.manufacturer)
    product = get_default_string_value(port_info.product)
    description = get_default_string_value(port_info.description)
    return (
        manufacturer == "u-blox AG - www.u-blox.com"
        and product == "u-blox GNSS receiver"
        and description == "u-blox GNSS receiver"
    )


def get_ports_of_ublox_gnss_receiver() -> tuple[str, ...]:
    port_list = comports(include_links=True)
    gnss_receiver_port_list = filter(is_ublox_gnss_receiver, port_list)
    return tuple([x.device for x in gnss_receiver_port_list])


def get_default_ublox_gnss_receiver_baudrate() -> int:
    return 9600


def get_default_ublox_gnss_receiver_timeout() -> float:
    return 0.1


def get_default_ublox_gnss_receiver_port_type() -> str:
    return "USB"


def get_ublox_gnss_receiver_serial() -> Serial:
    ublox_gnss_receiver_ports = get_ports_of_ublox_gnss_receiver()
    if len(ublox_gnss_receiver_ports) == 0:
        raise RuntimeError
    return Serial(
        port=ublox_gnss_receiver_ports[0],
        baudrate=get_default_ublox_gnss_receiver_baudrate(),
        timeout=get_default_ublox_gnss_receiver_timeout(),
    )


def is_ack_message_correct(ack_message: UBXMessage, sent_message: UBXMessage) -> bool:
    sent_message_identity: str = sent_message.identity
    ack_message_string = str(ack_message)
    match = re.search("msgID=([A-Z]{3}-[A-Z]{3})", ack_message_string)
    if match is None:
        raise RuntimeError
    try:
        ack_message_identity = str(match.group(1))
        return sent_message_identity == ack_message_identity
    except IndexError:
        raise RuntimeError


def send_message_to_ublox_gnss_receiver(
    serial: Serial, message: UBXMessage, ack_queue: queue.Queue[UBXMessage]
) -> None:
    serial.write(message.serialize())
    ack_message = ack_queue.get()
    if not is_ack_message_correct(ack_message, message):
        raise RuntimeError


def get_default_message_callback_for_ublox_gnss_receiver(
    message: UBXMessage | NMEAMessage,
) -> None:
    print(message)


def is_message_ublox_acknowledge(message: UBXMessage | NMEAMessage) -> bool:
    if isinstance(message, UBXMessage):
        return message.identity in ("ACK-ACK", "ACK-NAK")
    else:
        return False


def read_messages_from_ublox_gnss_receiver(
    serial: Serial,
    running_queue: queue.Queue[bool],
    ack_queue: queue.Queue[UBXMessage],
    callback: Callable[
        [UBXMessage | NMEAMessage], None
    ] = get_default_message_callback_for_ublox_gnss_receiver,
) -> None:
    ublox_reader = UBXReader(BufferedReader(serial))
    while not running_queue.empty():
        if serial.in_waiting:
            _, parsed_data = ublox_reader.read()
            if parsed_data:
                if is_message_ublox_acknowledge(parsed_data):
                    ack_queue.put(parsed_data)
                else:
                    callback(parsed_data)


def get_factory_reset_message_for_ublox_gnss_receiver() -> UBXMessage:
    return UBXMessage(
        "CFG",
        "CFG-CFG",
        SET,
        clearMask=b"\x1f\x1f\x00\x00",
        loadMask=b"\x1f\x1f\x00\x00",
        devBBR=1,
        devFlash=1,
        devEEPROM=1,
    )


def get_rtcm3_base_station_outputs_for_ublox_gnss_receiver() -> UBXMessage:
    layers = 7
    transaction = 0
    cfg_data = []
    for rtcm_type in (
        "1005",
        "1077",
        "1087",
        "1097",
        "1127",
        "1230",
        "4072_0",
        "4072_1",
    ):
        cfg = f"CFG_MSGOUT_RTCM_3X_TYPE{rtcm_type}_{get_default_ublox_gnss_receiver_port_type()}"
        cfg_data.append([cfg, 1])
    ubx = UBXMessage.config_set(layers, transaction, cfg_data)
    if isinstance(ubx, UBXMessage):
        return ubx
    else:
        raise RuntimeError


class UbloxGnssReceiver:
    def __init__(
        self,
        callback: Callable[
            [UBXMessage | NMEAMessage], None
        ] = get_default_message_callback_for_ublox_gnss_receiver,
    ) -> None:
        self.serial = get_ublox_gnss_receiver_serial()
        self.callback = callback
        self.ack_queue: queue.Queue[UBXMessage] = queue.Queue()
        self.running_queue: queue.Queue[bool] = queue.Queue()
        self.read_messages_thread = Thread(target=self.read_messages)

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

    def read_messages(self) -> None:
        read_messages_from_ublox_gnss_receiver(
            self.serial, self.running_queue, self.ack_queue, self.callback
        )

    def send_message(self, message: UBXMessage) -> None:
        send_message_to_ublox_gnss_receiver(self.serial, message, self.ack_queue)
