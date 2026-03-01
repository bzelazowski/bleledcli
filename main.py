import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from bleak import BleakClient, BleakScanner
from dotenv import load_dotenv, set_key

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

_USAGE = "Usage: python main.py <on|off|red|green|blue|white|10|50|100>"


@dataclass(frozen=True, slots=True)
class Command:
    frame: str  # Full hex string, e.g. "7E04010000000000EF"
    command: str  # CLI key, e.g. "on", "off", "red"
    description: str  # Human-readable label


_COMMAND_LIST: tuple[Command, ...] = (
    # Power
    Command("7E04010000000000EF", "off", "Turn off light"),
    Command("7E04010100000000EF", "on", "Turn on light"),
    # Colour
    Command("7E000503FF000000EF", "red", "Red light"),
    Command("7E00050300FF0000EF", "green", "Green light"),
    Command("7E0005030000FF00EF", "blue", "Blue light"),
    Command("7E000503FFFFFF00EF", "white", "White light"),
    # Brightness
    Command("7E00010A00000000EF", "10", "Brightness 10%"),
    Command("7E00013200000000EF", "50", "Brightness 50%"),
    Command("7E00016400000000EF", "100", "Brightness 100%"),
)

# lookup by command
COMMANDS: dict[str, Command] = {c.command.lower(): c for c in _COMMAND_LIST}


def find_command(key: str) -> Command:
    """Return the Command matching command (case-insensitive).

    If non existing command detected, returns proposal with defined commands
    """
    cmd = COMMANDS.get(key.lower())
    if cmd is None:
        log.error("Unknown command %r. Available are: %s", key, ", ".join(COMMANDS))
        sys.exit(1)
    return cmd


# ---------------------------------------------------------------------------
# Device configuration
# ---------------------------------------------------------------------------

ENV_FILE = Path(".env")


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    name: str
    address: str
    uuid: str


async def _scan_device() -> tuple[str, str]:
    """Discover the first LEDBLE device and return (name, address)."""
    log.info("Scanning for BLE devices…")
    devices = await BleakScanner.discover()
    led_devices = [d for d in devices if d.name and d.name.startswith("LEDBLE-")]
    if not led_devices:
        raise RuntimeError(
            "No LEDBLE device found — make sure it is powered on and in range."
        )
    device = led_devices[0]
    log.info("Found device: %s (%s)", device.name, device.address)
    return device.name, device.address


async def _scan_writable_uuid(address: str) -> str:
    """Connect to device address and return the first writable characteristic UUID."""
    log.info("Scanning services on %s…", address)
    async with BleakClient(address) as client:
        for service in client.services:
            for char in service.characteristics:
                if "write" in char.properties:
                    log.info("Found writable characteristic: %s", char.uuid)
                    return char.uuid
    raise RuntimeError("No writable characteristic found on device.")


async def _load_or_create_config() -> DeviceConfig:
    """Return device config, creating and persisting it from a scan if .env not available"""
    if not ENV_FILE.exists():
        name, address = await _scan_device()
        uuid = await _scan_writable_uuid(address)
        ENV_FILE.touch()
        set_key(str(ENV_FILE), "NAME", name)
        set_key(str(ENV_FILE), "ADDR", address)
        set_key(str(ENV_FILE), "UUID", uuid)
        log.info("Configuration detected and saved to %s", ENV_FILE)

    load_dotenv(str(ENV_FILE))
    name = os.getenv("NAME", "")
    address = os.getenv("ADDR", "")
    uuid = os.getenv("UUID", "")

    if not all((name, address, uuid)):
        raise RuntimeError(
            f"{ENV_FILE} is incomplete. Delete it manually and re-run to trigger a fresh scan."
        )

    return DeviceConfig(name=name, address=address, uuid=uuid)


# ---------------------------------------------------------------------------
# BLE communication
# ---------------------------------------------------------------------------


async def send_command(config: DeviceConfig, command: Command) -> None:
    """Send command to BLE device

    Sometimes device cuts communication after command recieved so this crazy error handling is intentional
    """
    from bleak.exc import BleakError  # local scope only

    log.info("Connecting to %s (%s)…", config.name, config.address)
    client = BleakClient(config.address)
    try:
        await client.connect()
        await client.write_gatt_char(
            config.uuid,
            bytes.fromhex(command.frame),
            response=False,
        )
        log.info("✓ %s", command.description)
    except (EOFError, BleakError) as error:
        # Real error (connect failed) command frame not sent.
        raise RuntimeError(f"BLE error before write completed: {error}") from error
    finally:
        try:
            await client.disconnect()
        except (EOFError, BleakError, Exception) as error:
            # Sometimes device does not close connection graceful way but cuts connection
            # It is very naughty device and has low social skills ;)
            log.debug("Disconnect notice (ignored): %s", error)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _run(key: str) -> None:
    """Execution logic"""
    command = find_command(key)
    config = await _load_or_create_config()
    await send_command(config, command)


def main() -> None:
    """User input validation and execution"""
    if len(sys.argv) != 2:
        print(_USAGE)
        sys.exit(1)

    try:
        asyncio.run(_run(sys.argv[1]))
    except RuntimeError as runtimeError:
        log.error("%s", runtimeError)
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Execution interrupted by user.")
        sys.exit()


if __name__ == "__main__":
    main()
