import csv
import math
import time
from collections import deque
from datetime import datetime

import serial
from serial.tools import list_ports
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle

# ---------------- Settings ----------------
BAUD = 9600
GAS_WARN = 260        # gas reading where the gauge turns yellow
GAS_DANGER = 330      # must match gasDanger in ZoneA_Uno.ino
GAS_MIN, GAS_MAX = 150, 600   # range shown on the toxic-level gauge
POINTS = 150          # about 30 s of graph history
CALL_DELAY = 3        # seconds of "Calling..." before "alerted"
NO_DATA_SECS = 5
PORT_WORDS = ("arduino", "ch340", "ch341", "usb-serial", "usb serial", "wch", "ch9102", "cp210")

GREEN, AMBER, RED, GRAY = "#2e7d32", "#f9a825", "#c62828", "#757575"
BLUE, ORANGE, OFF = "#1565c0", "#ef6c00", "#b0b0b0"

# ---------------- State ----------------
links = {}            # port name -> serial object
last_scan = [0.0]
zones = {
    "A": {"seen": 0.0, "gas": None, "alarm": 0, "door": 0, "fan": 0, "pump": 0,
          "lights": 0, "inside": "nobody", "alarm_start": 0.0, "called": False},
    "B": {"seen": 0.0, "flame": 0, "alarm": 0, "door": 0, "lights": 0,
          "alarm_start": 0.0, "called": False},
}
gas_hist = deque([math.nan] * POINTS, maxlen=POINTS)
flame_hist = deque([math.nan] * POINTS, maxlen=POINTS)
events = deque(maxlen=9)

log_file = open("blackbox.csv", "a", newline="")
log = csv.writer(log_file)


def add_event(text):
    events.appendleft(f"{datetime.now():%H:%M:%S}  {text[:52]}")
    log.writerow([datetime.now().isoformat(timespec="seconds"), text])
    log_file.flush()


# ---------------- Serial: find and keep both boards connected ----------------
def scan_ports():
    last_scan[0] = time.time()
    for p in list_ports.comports():
        if p.device in links:
            continue
        text = f"{p.description} {p.manufacturer}".lower()
        if any(w in text for w in PORT_WORDS):
            try:
                links[p.device] = serial.Serial(p.device, BAUD, timeout=0.05)
                print(f"Connected: {p.device} ({p.description})")
            except Exception as err:
                print(f"Could not open {p.device}: {err}")


def drop(port):
    try:
        links[port].close()
    except Exception:
        pass
    links.pop(port, None)
    add_event(f"USB lost on {port}")


def parse(line):
    if line.startswith("EV|"):
        parts = line.split("|", 2)
        if len(parts) == 3:
            add_event(f"Zone {parts[1]}: {parts[2]}")
        return
    if line[:2] not in ("A|", "B|"):
        return
    zone = zones[line[0]]
    was_alarm = zone["alarm"]
    for item in line[2:].split("|"):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        if key == "inside":
            zone["inside"] = val.strip() or "nobody"
        else:
            try:
                zone[key] = int(val)
            except ValueError:
                pass
    zone["seen"] = time.time()
    if zone["alarm"] and not was_alarm:
        zone["alarm_start"] = time.time()
        zone["called"] = False


def read_all():
    if time.time() - last_scan[0] > 2:
        scan_ports()
    for port, ser in list(links.items()):
        try:
            while ser.in_waiting:
                raw = ser.readline().decode(errors="ignore").strip()
                if raw:
                    parse(raw)
        except Exception:
            drop(port)


def online(z):
    return time.time() - zones[z]["seen"] < NO_DATA_SECS


# ---------------- Window layout ----------------
fig = plt.figure(figsize=(13.5, 7.6), facecolor="#f4f6f8")
fig.canvas.manager.set_window_title("Smart Fire Response - Live Dashboard")
fig.text(0.5, 0.955, "Smart Fire Response System  |  Live Building Dashboard",
         ha="center", fontsize=18, weight="bold", color="#1f2a36")


def panel(x0, w, title):
    fig.patches.append(Rectangle((x0, 0.47), w, 0.45, transform=fig.transFigure,
                                 facecolor="white", edgecolor="#d0d7de", lw=1, zorder=-5))
    fig.text(x0 + 0.015, 0.89, title, fontsize=13, weight="bold", color="#1f2a36", va="top")


def chip(x, y, size=10):
    return fig.text(x, y, "", ha="center", va="center", fontsize=size, weight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.45", facecolor=OFF, edgecolor="none"))


def set_chip(c, text, color):
    c.set_text(text)
    c.get_bbox_patch().set_facecolor(color)


panel(0.025, 0.465, "ZONE A  -  KITCHEN   (MQ2 gas / smoke sensor)")
panel(0.51, 0.465, "ZONE B  -  LIVING ROOM   (IR flame sensor)")

# Zone A
a_status = chip(0.2575, 0.80, 20)
a_level = fig.text(0.04, 0.715, "", fontsize=11, weight="bold", color="#1f2a36")
gauge = fig.add_axes([0.04, 0.645, 0.435, 0.055], zorder=5)


def pct(v):
    return max(0.0, min(100.0, (v - GAS_MIN) / (GAS_MAX - GAS_MIN) * 100))


gauge.add_patch(Rectangle((0, 0), pct(GAS_WARN), 1, color="#c8e6c9"))
gauge.add_patch(Rectangle((pct(GAS_WARN), 0), pct(GAS_DANGER) - pct(GAS_WARN), 1, color="#fff3c4"))
gauge.add_patch(Rectangle((pct(GAS_DANGER), 0), 100 - pct(GAS_DANGER), 1, color="#ffcdd2"))
gauge_bar = gauge.add_patch(Rectangle((0, 0.25), 0, 0.5, color=GREEN))
gauge.set_xlim(0, 100)
gauge.set_ylim(0, 1)
gauge.set_yticks([])
gauge.set_xticks([0, pct(GAS_WARN), pct(GAS_DANGER), 100])
gauge.set_xticklabels(["0%", "warning", "danger", "100%"], fontsize=8)
for s in gauge.spines.values():
    s.set_visible(False)
a_door, a_fan, a_pump, a_lights = (chip(x, 0.555) for x in (0.095, 0.205, 0.315, 0.425))
a_inside = fig.text(0.04, 0.495, "", fontsize=11, color="#1f2a36")

# Zone B
b_status = chip(0.7425, 0.80, 20)
b_flame = chip(0.7425, 0.665, 14)
b_door, b_lights = (chip(x, 0.555) for x in (0.65, 0.835))
fig.text(0.525, 0.495, "Sensor: IR flame detector  |  door: auto-unlock on fire",
         fontsize=10, color="#555555")

# Graph
graph = fig.add_axes([0.06, 0.08, 0.50, 0.32])
line_gas, = graph.plot(range(POINTS), list(gas_hist), color=RED, lw=2, label="Zone A gas level")
line_flame, = graph.step(range(POINTS), list(flame_hist), color=ORANGE, lw=2, label="Zone B flame (on/off)")
graph.axhline(GAS_WARN, color=AMBER, ls="--", lw=1, label="warning level")
graph.axhline(GAS_DANGER, color=RED, ls="--", lw=1, label="danger level")
graph.set_xlim(0, POINTS - 1)
graph.set_ylim(0, GAS_MAX)
graph.set_xticks([])
graph.set_xlabel("Last ~30 seconds")
graph.set_ylabel("Sensor reading")
graph.legend(loc="upper left", fontsize=8, ncol=2)
graph.grid(alpha=0.3)

# Emergency call + event log
call_box = chip(0.785, 0.425, 13)
log_ax = fig.add_axes([0.60, 0.04, 0.38, 0.29])
log_ax.axis("off")
log_ax.set_title("Event log (black box)", loc="left", fontsize=11, weight="bold")
log_text = log_ax.text(0, 1, "", va="top", fontsize=9.5, family="monospace")


# ---------------- Update loop ----------------
def update(_frame):
    read_all()
    za, zb = zones["A"], zones["B"]
    a_on, b_on = online("A"), online("B")

    # Zone A
    gas = za["gas"]
    if not a_on or gas is None:
        set_chip(a_status, "NO DATA - check Uno USB", GRAY)
        a_level.set_text("Toxic gas level: --")
        gauge_bar.set_width(0)
        gas_hist.append(math.nan)
    else:
        p = pct(gas)
        if za["alarm"]:
            set_chip(a_status, "GAS / SMOKE ALERT!  EVACUATE", RED)
            level, col = "DANGER", RED
        elif gas >= GAS_WARN:
            set_chip(a_status, "WARNING - gas rising", AMBER)
            level, col = "WARNING", AMBER
        else:
            set_chip(a_status, "SAFE", GREEN)
            level, col = "SAFE", GREEN
        a_level.set_text(f"Toxic gas level: {p:.0f}%  ({level})   raw {gas}")
        gauge_bar.set_width(p)
        gauge_bar.set_color(col)
        gas_hist.append(gas)
    set_chip(a_door, "DOOR OPEN" if za["door"] else "DOOR LOCKED", ORANGE if za["door"] else BLUE)
    set_chip(a_fan, "FAN ON" if za["fan"] else "FAN OFF", BLUE if za["fan"] else OFF)
    set_chip(a_pump, "SPRINKLER ON" if za["pump"] else "SPRINKLER OFF", BLUE if za["pump"] else OFF)
    set_chip(a_lights, "EXIT LIGHTS ON" if za["lights"] else "EXIT LIGHTS OFF", AMBER if za["lights"] else OFF)
    a_inside.set_text(f"People inside (RFID): {za['inside']}")

    # Zone B
    if not b_on:
        set_chip(b_status, "NO DATA - check Nano USB", GRAY)
        set_chip(b_flame, "FLAME: --", OFF)
        flame_hist.append(math.nan)
    else:
        if zb["alarm"]:
            set_chip(b_status, "FIRE DETECTED!  EVACUATE", RED)
        else:
            set_chip(b_status, "SAFE", GREEN)
        set_chip(b_flame, "FLAME DETECTED" if zb["flame"] else "NO FLAME", RED if zb["flame"] else GREEN)
        flame_hist.append(GAS_MAX * 0.9 if zb["flame"] else 0)
    set_chip(b_door, "DOOR OPEN" if zb["door"] else "DOOR LOCKED", ORANGE if zb["door"] else BLUE)
    set_chip(b_lights, "EXIT LIGHTS ON" if zb["lights"] else "EXIT LIGHTS OFF", AMBER if zb["lights"] else OFF)

    # Emergency call (simulated - no real call is made)
    active = [(k, z) for k, z in zones.items() if z["alarm"] and online(k)]
    if active:
        names = " + ".join(k for k, _ in active)
        waited = time.time() - min(z["alarm_start"] for _, z in active)
        if waited < CALL_DELAY:
            set_chip(call_box, f"Calling Fire Service (999){'.' * (int(waited * 2) % 4)}", ORANGE)
        else:
            set_chip(call_box, f"Fire Service alerted (999)  -  Zone {names}", "#8b0000")
            for k, z in active:
                if not z["called"]:
                    z["called"] = True
                    extra = f", inside: {zones['A']['inside']}" if k == "A" else ""
                    add_event(f"Fire Service alerted - Zone {k}{extra}")
    else:
        call_box.set_text("")
        call_box.get_bbox_patch().set_facecolor("none")

    line_gas.set_ydata(list(gas_hist))
    line_flame.set_ydata(list(flame_hist))
    log_text.set_text("\n".join(events))
    return ()


add_event("Dashboard started")
scan_ports()
animation = FuncAnimation(fig, update, interval=200, cache_frame_data=False)
plt.show()

for s in list(links.values()):
    try:
        s.close()
    except Exception:
        pass
log_file.close()
