#!/usr/bin/env python3
"""Audit logical USB3 lane selection; this does not inspect routed copper.

Run after the USB builder has finished writing its inventory and overrides:
    python3 -B source/fabrication/audit_usb3_lanes.py

Primary IC pin numbers and switch truth tables below are independent of the
project's symbol names. Independent P/N inversions are allowed for SuperSpeed;
a TX/RX crossover or selection of the wrong connector lane is a failure.
"""
import argparse
import collections
import datetime
import hashlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = (
    "source/generator/usb3_frontend.py",
    "source/generator/usb3_frontend_routed.py",
)
PRIMARY_SOURCES = {
    "HD3SS3220": {
        "url": "https://www.ti.com/lit/ds/symlink/hd3ss3220.pdf",
        "revision": "SLLSES1E, July 2025",
        "references": "Sections 6.2, 6.3.4; Figure 7-3; pin functions",
    },
    "TPS25810": {
        "url": "https://www.ti.com/lit/ds/symlink/tps25810.pdf",
        "revision": "SLVSCR1C, July 2017",
        "references": "Section 7.3.3.7, Table 6, Figure 15; pin functions",
    },
    "HD3SS3212": {
        "url": "https://www.ti.com/lit/ds/symlink/hd3ss3212.pdf",
        "revision": "SLASE74F, September 2016",
        "references": "Section 9.4, Table 1; pin functions",
    },
    "USB5744": {
        "url": "https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DesignChecklist/USB5744-Hardware-Design-Checklist-DS000029701.pdf",
        "revision": "DS00002970B, 2024",
        "references": "Sections 4.1, 4.2; Figure 4-2; page 3 Note 2 permits SS TX/RX pair polarity inversions",
    },
}
# Each selected mux edge is a pair of physical pin numbers. Connector tuples
# are physical positive/negative contacts per the Type-C receptacle convention.
PORTS = (
    ("UP", "J500", "U501", {"TX": ("47", "48"), "RX": ("50", "51")}, (
        ("CC1", "DIR=1", {
            "TX": (("6", "17"), ("7", "16")),
            "RX": (("9", "15"), ("10", "14")),
        }, {"TX": ("A2", "A3"), "RX": ("B11", "B10")}),
        ("CC2", "DIR=0", {
            "TX": (("6", "21"), ("7", "20")),
            "RX": (("9", "19"), ("10", "18")),
        }, {"TX": ("B2", "B3"), "RX": ("A11", "A10")}),
    )),
    ("CAM", "J501", "U503", {"TX": ("10", "11"), "RX": ("13", "14")}, (
        ("CC1", "POL=HiZ/pullup→SEL=H→C", {
            "TX": (("3", "15"), ("4", "14")),
            "RX": (("7", "13"), ("8", "12")),
        }, {"TX": ("A2", "A3"), "RX": ("B11", "B10")}),
        ("CC2", "POL=L→SEL=L→B", {
            "TX": (("3", "19"), ("4", "18")),
            "RX": (("7", "17"), ("8", "16")),
        }, {"TX": ("B2", "B3"), "RX": ("A11", "A10")}),
    )),
)


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES}


def load_snapshot(name, relative_path, contents):
    """Execute the hashed source bytes, never a potentially stale pyc file."""
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / relative_path)
    sys.modules[name] = module
    exec(compile(contents, module.__file__, "exec"), module.__dict__)
    return module


def control_checks(parts, byref):
    expected = {
        "J500": {"A5": "UP_CC1", "B5": "UP_CC2"},
        "J501": {"A5": "CAM_CC1", "B5": "CAM_CC2"},
        "U501": {"1": "UP_CC2", "2": "UP_CC1", "4": "GND",
                 "11": "UP_DIR", "12": "GND"},
        "U502": {"11": "CAM_CC1", "13": "CAM_CC2",
                 "18": "CAM_POL", "19": "CAM_UFP_N"},
        "U503": {"2": "CAM_UFP_N", "9": "CAM_POL"},
    }
    for ref, pins in expected.items():
        for pin, net in pins.items():
            actual = byref[ref]["pins"].get(pin)
            require(actual == net, f"{ref}.{pin}: expected {net}, found {actual}")
    for signal in ("UP_DIR", "CAM_POL", "CAM_UFP_N"):
        require(any(part["ref"].startswith("R") and
                    set(part["pins"].values()) == {"+3V3_USB", signal}
                    for part in parts), f"Missing 3.3V pull-up for {signal}")
    return {"status": "pass", "physical_pin_connections": expected,
            "required_pullups_to_3V3": ["UP_DIR", "CAM_POL", "CAM_UFP_N"]}


def reachable(graph, start):
    queue = collections.deque([start])
    previous = {start: None}
    while queue:
        node = queue.popleft()
        for neighbor in sorted(graph[node]):
            if neighbor not in previous:
                previous[neighbor] = node
                queue.append(neighbor)
    return previous


def audit_variant(parts):
    byref = {part["ref"]: part for part in parts}
    require(len(byref) == len(parts), "Duplicate reference in inventory")
    controls = control_checks(parts, byref)
    checks = []
    for prefix, connector, mux, hubpairs, states in PORTS:
        for cc, control, channels, expected in states:
            graph = collections.defaultdict(set)

            def connect(a, b):
                graph[a].add(b)
                graph[b].add(a)

            for part in parts:
                nets = list(part["pins"].values())
                if (part["ref"].startswith("C") and len(nets) == 2 and
                        all(net.startswith(prefix + "_") and
                            ("_TX" in net or "_RX" in net) for net in nets)):
                    connect(*nets)
            for edges in channels.values():
                for a, b in edges:
                    connect(byref[mux]["pins"][a], byref[mux]["pins"][b])
            for direction, hubpins in hubpairs.items():
                paths = []
                for hubpin in hubpins:
                    start = byref["U500"]["pins"][hubpin]
                    previous = reachable(graph, start)
                    endpoints = [(pin, net) for pin, net in byref[connector]["pins"].items()
                                 if net in previous]
                    require(len(endpoints) == 1,
                            f"{prefix}/{cc}/{direction}/U500.{hubpin}: expected one connector contact, found {endpoints}")
                    endpoint, net = endpoints[0]
                    chain = [net]
                    while chain[-1] != start:
                        chain.append(previous[chain[-1]])
                    paths.append({"hub_pin": hubpin, "connector_pin": endpoint,
                                  "net_chain": list(reversed(chain))})
                actual = tuple(path["connector_pin"] for path in paths)
                require(set(actual) == set(expected[direction]),
                        f"{prefix}/{cc}/{direction}: expected pair {expected[direction]}, found {actual}")
                checks.append({"port": prefix, "detected_cc": cc,
                               "control_state": control, "direction_relative_to_hub": direction,
                               "connector": connector,
                               "expected_connector_pair_p_n": expected[direction],
                               "paths_from_physical_hub_p_n": paths,
                               "pair_inverted": actual == expected[direction][::-1]})
    return {"part_count": len(parts), "control_checks": controls,
            "orientation_paths": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "outputs/usb3-design/lane-orientation-audit.json")
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "source/generator"))
    snapshots = {name: (ROOT / name).read_bytes() for name in SOURCE_FILES}
    hashes = {name: hashlib.sha256(contents).hexdigest()
              for name, contents in snapshots.items()}
    base = load_snapshot("usb3_frontend", SOURCE_FILES[0], snapshots[SOURCE_FILES[0]])
    routed = load_snapshot("usb3_frontend_routed", SOURCE_FILES[1], snapshots[SOURCE_FILES[1]])
    require(hashes == source_hashes(), "Source changed during import; rerun after builder finishes")
    variants = {"inventory": audit_variant(base.PARTS),
                "routed_overrides": audit_variant(routed.PARTS)}
    require(hashes == source_hashes(), "Source changed during audit; rerun after builder finishes")
    result = {
        "status": "pass",
        "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_sha256": hashes,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Logical physical-IC-pin channel assignments through series capacitors to connector pins. Does not prove routed copper, component ratings, signal integrity or physical enumeration.",
        "primary_sources": PRIMARY_SOURCES,
        "variants": variants,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    count = sum(len(variant["orientation_paths"]) for variant in variants.values())
    print(f"PASS: {count} logical channel paths and both ports' orientation controls; {args.output}")
    print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
