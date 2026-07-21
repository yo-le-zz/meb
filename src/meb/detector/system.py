import platform

# Architecture machine -> architecture Debian
ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "AMD64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "armv7l": "armhf",
    "armv6l": "armhf",
    "i386": "i386",
    "i686": "i386",
}


def get_machine_architecture() -> str:
    return platform.machine()


def get_debian_architecture() -> str:
    machine = platform.machine()
    return ARCH_MAP.get(machine, machine)