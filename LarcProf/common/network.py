import os
from larccommon.network import detect_network, NetworkMode


def network_mode_color(mode: NetworkMode) -> str:
    return {
        NetworkMode.INTRANET: '#27ae60',
        NetworkMode.INTERNET: '#2980b9',
        NetworkMode.OFFLINE: '#e67e22',
    }.get(mode, '#7f8c8d')
