# 💡 BLELEDCLI Command line interface

A lightweight Python CLI tool for controlling LEDBLE Bluetooth smart lights from the command line

---

## Motivation
- Command line usage - easy integration with cron or some keybinds on work station
- No strange apps on phone or computer

---

## Installation

```bash
git clone https://github.com/bzelazowski/bleledcli.git
cd bleledcli
uv sync
```
---

## Requirements

- Python **3.13+** with uv installed
- Bluetooth adapter available on your computer
- A powered-on **LEDBLE** device in range

---

## Usage

```bash
uv run main.py <command>
or
./bleled.sh <command>
```

---

## First Run — Device Discovery

On the **first run**, if no `.env` file is present, the tool will automatically:

1. Scan for nearby BLE devices matching the `LEDBLE-` prefix
2. Connect and discover the writable characteristic UUID
3. Save the configuration to `.env` for all future runs

To **re-pair** with a different device, simply delete `.env` and run again:

```bash
rm .env
uv run main.py on
```

## Notes

Frame structure

```
mode: int
    00 = off
    01 = on - bright 01
    FF = brightest

color: int 0-255

7E 04 01 00 00 00 00 00 EF
      │  │  │  │  │
      │  │  │  │  └-- blue (0-255)
      │  │  │  └-- green (0-255)
      │  │  └-- red (0-255)
      │  └-- brightness: 00=off, 100=max 
      └-- mode TODO: some animations
```

---

## License

MIT
