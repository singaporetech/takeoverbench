"""
find_spawns.py — run once while CARLA is open to find spawn point indices.
Draws numbered markers in the CARLA viewport for 60 seconds.
"""

import logging
import carla

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()

spawn_points = world.get_map().get_spawn_points()
logger.info("Total spawn points: %d", len(spawn_points))

# Draw index numbers in CARLA window for 60 seconds
for i, sp in enumerate(spawn_points):
    world.debug.draw_string(
        sp.location, str(i),
        color=carla.Color(255, 255, 0),
        life_time=60.0,
    )
    logger.info("[%d] x=%.1f, y=%.1f, yaw=%.1f", i, sp.location.x, sp.location.y, sp.rotation.yaw)

input("Look at CARLA window, find a highway straight point, note the index. Press Enter to quit.")
