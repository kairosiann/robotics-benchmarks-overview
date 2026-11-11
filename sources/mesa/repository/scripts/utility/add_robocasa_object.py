#!/usr/bin/env python3
"""Add a RoboCasa365 object to the unified asset bundle.

Front door for extending the object set (see docs/appendix/objects.md). Copies a
source object directory into the right asset tree, validates that it loads, and
prints the `object_info.py` registration snippet.

Default target is BiMESA (canonical, dual-arm): `objects/objaverse/` or,
with --aigen, `objects/aigen_objs/`. The source dir must contain `model.xml`
(with a `reg_bbox` geom), `visual/`, and `collision/`.

With --mesa, also writes the single-arm MESA variant under
`objects/robocasa[_ai]/`, synthesizing the bottom/top/horizontal_radius sites
from the `reg_bbox` extents. Visualize the result (scripts/visualize.py) before
relying on it for single-arm data.
"""
import argparse
import os
import shutil
import xml.etree.ElementTree as ET

from mesa.sim import ASSETS_ROOT


def _read_reg_bbox(model_xml):
    """Return (pos, half_size) of the reg_bbox geom, each a 3-tuple of floats."""
    root = ET.parse(model_xml).getroot()
    for geom in root.iter("geom"):
        if geom.get("name") == "reg_bbox":
            pos = tuple(float(v) for v in geom.get("pos", "0 0 0").split())
            size = tuple(float(v) for v in geom.get("size").split())
            return pos, size
    raise ValueError(f"no reg_bbox geom in {model_xml} (not a BiMESA object?)")


def _synthesize_mesa(src_dir, dst_dir):
    """Copy the object and add bottom/top/horizontal_radius sites from reg_bbox."""
    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
    model_xml = os.path.join(dst_dir, "model.xml")
    (px, py, pz), (sx, sy, sz) = _read_reg_bbox(model_xml)
    tree = ET.parse(model_xml)
    # sites go on the outer body (sibling of the inner <body name="object">),
    # matching the MESA layout
    body = tree.getroot().find(".//worldbody/body")
    for name, pos in [
        ("bottom_site", (px, py, pz - sz)),
        ("top_site", (px, py, pz + sz)),
        ("horizontal_radius_site", (sx, sy, 0.0)),
    ]:
        ET.SubElement(body, "site", {
            "name": name, "rgba": "0 0 0 0", "size": "0.005",
            "pos": f"{pos[0]} {pos[1]} {pos[2]}",
        })
    tree.write(model_xml)


def _validate(model_xml, name):
    from mesa.sim.envs.objects.robocasa_objects import RobocasaObject
    obj = RobocasaObject(mjcf_path=model_xml, name=name)
    ho = list(obj.horizontal_offset)
    assert all(v == v for v in ho) and obj.horizontal_radius > 1e-4, "degenerate geometry"
    return obj.horizontal_radius, ho


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="source object instance dir (with model.xml)")
    ap.add_argument("--category", required=True, help="object category, e.g. 'apple'")
    ap.add_argument("--name", help="instance dir name (default: basename of --src)")
    ap.add_argument("--aigen", action="store_true", help="target aigen_objs/ instead of objaverse/")
    ap.add_argument("--mesa", action="store_true", help="also emit the single-arm MESA variant")
    ap.add_argument("--assets-root", default=str(ASSETS_ROOT))
    args = ap.parse_args()

    inst = args.name or os.path.basename(os.path.normpath(args.src))
    src_xml = os.path.join(args.src, "model.xml")
    if not os.path.isfile(src_xml):
        raise SystemExit(f"no model.xml in {args.src}")

    r_tree = "aigen_objs" if args.aigen else "objaverse"
    r_dst = os.path.join(args.assets_root, "objects", r_tree, args.category, inst)
    shutil.copytree(args.src, r_dst, dirs_exist_ok=True)
    hr, ho = _validate(os.path.join(r_dst, "model.xml"), f"add_{inst}")
    print(f"[BiMESA] added {r_tree}/{args.category}/{inst}  (horizontal_radius={hr:.4f})")

    if args.mesa:
        m_tree = "robocasa_ai" if args.aigen else "robocasa"
        m_dst = os.path.join(args.assets_root, "objects", m_tree, args.category, inst)
        _synthesize_mesa(args.src, m_dst)
        print(f"[MESA] added {m_tree}/{args.category}/{inst}  (sites from reg_bbox — VISUALIZE before use)")

    key = ("robocasa_ai_" if args.aigen else "robocasa_") + inst
    print("\nRegister the category in mesa/sim/envs/objects/object_info.py, e.g.:")
    print(f'    "{args.category}": {{')
    print(f'        "graspable": True, "on_dest": False, "types": ("<tag>",),')
    print(f'        # ... see neighbouring entries for the full field set')
    print(f'    }},')
    print(f"\nInstance key the simulator will use: {key}")
    print("Visualize:  uv run scripts/visualize.py --object-names", key)


if __name__ == "__main__":
    main()
