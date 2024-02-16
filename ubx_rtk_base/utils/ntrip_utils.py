import subprocess


def start_publishing_rtcm_messages(
    ntrips_mountpoint: str,
    ntrips_password: str,
    tcp_address: str = "127.0.0.1",
    tcp_port: int = 2101,
    ntrips_address: str = "rtk2go.com",
    ntrips_port: int = 2101,
    message_format: str = "rtcm3",
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        f"str2str "
        f"-in tcpcli://{tcp_address}:{tcp_port}#{message_format} "
        f"-out ntrips://:{ntrips_password}@{ntrips_address}:{ntrips_port}/{ntrips_mountpoint}#{message_format}",
        shell=True,
    )
