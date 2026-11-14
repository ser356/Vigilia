"""Medidas en cm, independientes del editor para comprobar recorridos y escaleras."""
LEVELS = (("basement", -300.0), ("ground", 0.0), ("upper", 300.0))
FLOOR_HEIGHT = 300.0
WALL_HEIGHT = 280.0
HALL = (870.0, 1900.0, -395.0, -175.0)
BAY = (1900.0, 2440.0, -1000.0, 600.0)
STAIR_HOLE = (1940.0, 2360.0, -180.0, 260.0)
RISER, TREAD, STEPS = 15.0, 28.0, 10
ROOM_NAMES = {
    "basement": ("archive", "workshop", "laundry", "storage"),
    "ground": ("library", "drawing_room", "dining_room", "study"),
    "upper": ("master_bedroom", "nursery", "guest_bedroom", "upstairs_bath"),
}


def rooms(level):
    bounds = ((870, 1380, -175, 600), (1380, 1900, -175, 600),
              (870, 1380, -1000, -395), (1380, 1900, -1000, -395))
    return [(name, bounds[i], "N" if i < 2 else "S")
            for i, name in enumerate(ROOM_NAMES[level])]


def stair_blocks(base_z):
    """Dos tramos de 150 cm, rellano de 160 cm; paso util de 170 cm."""
    for i in range(STEPS):
        yield ((1940, -180 + i * TREAD, base_z + (i + 1) * RISER - 20),
               (2110, -180 + (i + 1) * TREAD, base_z + (i + 1) * RISER))
    yield ((1940, 100, base_z + 130), (2360, 260, base_z + 150))
    for i in range(STEPS):
        yield ((2190, 100 - (i + 1) * TREAD, base_z + 150 + (i + 1) * RISER - 20),
               (2360, 100 - i * TREAD, base_z + 150 + (i + 1) * RISER))
