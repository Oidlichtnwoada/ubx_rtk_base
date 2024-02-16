import functools
import queue
import socket
import threading


def start_rtcm3_tcp_server_streaming(
    rtcm3_bytes_queue: queue.Queue[bytes],
    running_queue: queue.Queue[bool],
    server: socket.socket,
) -> None:
    conn, _ = server.accept()
    while not rtcm3_bytes_queue.empty():
        _ = rtcm3_bytes_queue.get()
    while not running_queue.empty():
        while not rtcm3_bytes_queue.empty():
            current_rtcm3_message_bytes = rtcm3_bytes_queue.get()
            conn.sendall(current_rtcm3_message_bytes)


def get_rtcm3_tcp_server_thread(
    rtcm3_bytes_queue: queue.Queue[bytes],
    running_queue: queue.Queue[bool],
    tcp_address: str = "127.0.0.1",
    tcp_port: int = 2101,
    connect_timeout_seconds: float = 10.0,
) -> threading.Thread:
    server = socket.create_server((tcp_address, tcp_port), family=socket.AF_INET)
    server.settimeout(connect_timeout_seconds)
    return threading.Thread(
        target=functools.partial(
            start_rtcm3_tcp_server_streaming,
            rtcm3_bytes_queue=rtcm3_bytes_queue,
            running_queue=running_queue,
            server=server,
        )
    )
