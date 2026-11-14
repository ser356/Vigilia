"""Pruebas estructurales del generador, sin necesitar una instalacion de Unreal.

No sustituyen PIE: comprueban huecos, soporte y espacio para el personaje de 178 cm.
"""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts"))


class Dummy:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return lambda *a, **kw: Dummy()


fake_unreal = types.ModuleType("unreal")
for name in ("SpotLight", "SpotLightComponent", "VGLamp", "VGLightSwitch", "VGRoomAudio"):
    setattr(fake_unreal, name, type(name, (Dummy,), {}))
fake_unreal.ComponentMobility = Dummy(MOVABLE=0)
fake_unreal.LightUnits = Dummy(LUMENS=0)
sys.modules["unreal"] = fake_unreal
import vg_mansion
from vg_mansion_layout import LEVELS, rooms


class MansionStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boxes = []

        def box(key, mn, mx, material, **kw):
            assert all(mx[i] > mn[i] for i in range(3)), key
            if kw.get("collision", True):
                cls.boxes.append((key, tuple(mn), tuple(mx)))
            return Dummy()

        cls.v = Dummy(STATE={"house": {"doors": {"door_end": Dummy(), "door_bathroom": Dummy()}, "lamps": {}}},
                      DOOR_W=88, DOOR_H=205, JAMB=6, box=box, ML=Dummy(), eal=Dummy(),
                      V=lambda x, y, z: Dummy(x=x, y=y, z=z), R=lambda **kw: Dummy(),
                      spawn_marked=lambda klass, *a, **kw: klass(),
                      actor_sub=Dummy(get_all_level_actors=lambda: []),
                      spawn_house_door=lambda *a, **kw: Dummy(get_actor_location=lambda: Dummy(x=0, y=0, z=1)),
                      safe_set=lambda *a: None, set_bool=lambda *a: None)
        mats = {key: key for key in ("floor", "wall_XZ", "wall_YZ", "trim", "glass", "switch", "ceiling", "rug")}
        vg_mansion.build(cls.v, {}, mats, [])

    def assert_clear(self, x, y, z):
        """Conservador: caja de 52 x 52 x 178 cm, tolerancia de un escalon (15 cm)."""
        for key, mn, mx in self.boxes:
            overlap_xy = mn[0] < x + 26 and mx[0] > x - 26 and mn[1] < y + 26 and mx[1] > y - 26
            self.assertFalse(overlap_xy and mx[2] > z + 15.1 and mn[2] < z + 178, (key, x, y, z))

    def assert_supported(self, x, y, z):
        self.assertTrue(any(mn[0] <= x <= mx[0] and mn[1] <= y <= mx[1] and abs(mx[2] - z) < .1
                            for _, mn, mx in self.boxes), (x, y, z))

    def test_two_flights_and_turn_have_headroom(self):
        for base in (-300, 0):
            for i in range(10):
                for x, y, z in ((2025, -180 + (i + .5) * 28, base + (i + 1) * 15),
                                (2275, 100 - (i + .5) * 28, base + 150 + (i + 1) * 15)):
                    self.assert_supported(x, y, z)
                    self.assert_clear(x, y, z)
            for x in range(2025, 2276, 25):
                self.assert_supported(x, 180, base + 150)
                self.assert_clear(x, 180, base + 150)

    def test_all_rooms_accessible_from_gallery(self):
        for level, z in LEVELS:
            for name, (x0, x1, y0, y1), side in rooms(level):
                cx = (x0 + x1) / 2
                end = -90 if side == "N" else -480
                for y in range(-285, end, 10 if side == "N" else -10):
                    self.assert_supported(cx, y, z)
                    self.assert_clear(cx, y, z)

    def test_gallery_and_stair_landings_connect(self):
        for _, z in LEVELS:
            for x in range(920, 2300, 20):
                self.assert_supported(x, -285, z)
                self.assert_clear(x, -285, z)
            for x in (2025, 2275):
                self.assert_clear(x, -210, z)

    def test_original_wing_has_a_clear_connection(self):
        for x in range(870, 951, 10):
            self.assert_clear(x, -285, 0)


if __name__ == "__main__":
    unittest.main()
