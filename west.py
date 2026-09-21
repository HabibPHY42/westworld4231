"""
RED WEST 3D: ASSET FILTERED EDITION (Panda3D)

Modifications:
- Removed 'tree1' asset loading (range 2..6 now used).
- Retained removal of 'bandit4', 'npc8', and 'mountain3'.
"""

import sys
import math
import random
import ctypes

# Force Windows to route Python through high-performance GPU
try:
    ctypes.c_ulong.in_dll(ctypes.CDLL('nvapi64.dll'), 'NvOptimusEnablement').value = 0x00000001
except Exception:
    pass

try:
    ctypes.c_ulong.in_dll(ctypes.CDLL('AmdPowerXpressRequestHighPerformance'), 'AmdPowerXpressRequestHighPerformance').value = 0x00000001
except Exception:
    pass

from panda3d.core import loadPrcFileData
loadPrcFileData("", "gltf-skip-animations true")
loadPrcFileData("", "framebuffer-hardware true")
loadPrcFileData("", "sync-video true")

from direct.showbase.ShowBase import ShowBase
from panda3d.core import DirectionalLight, AmbientLight, WindowProperties, CardMaker, TextNode, Fog
from direct.gui.OnscreenText import OnscreenText

try:
    import gltf
except ImportError:
    gltf = None

try:
    import simplepbr
except ImportError:
    simplepbr = None


class RedWest3D(ShowBase):
    def __init__(self):
        super().__init__()

        gsg = self.win.getGsg()
        if gsg:
            print(f"[GPU ACTIVE] {gsg.getDriverVendor()} - {gsg.getDriverRenderer()}")

        if simplepbr:
            try:
                simplepbr.init(enable_shadows=False)
            except Exception:
                pass

        self.win.setClearColor((0.42, 0.65, 0.88, 1.0))
        props = WindowProperties()
        props.setTitle("Red West 3D - Populated World")
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        # Camera far plane distance for high performance culling
        self.camLens.setFar(1200.0)

        self.ammo = 6
        self.kills = 0
        self.is_reloading = False

        self.keys = {"w": False, "s": False, "a": False, "d": False}
        self.setup_inputs()

        self.templates = {}
        self.valid_trees = []
        self.valid_mountains = []

        self.setup_lighting()
        self.preload_templates()
        self.setup_environment()
        self.setup_character()

        self.ui_text = OnscreenText(
            text=f"Ammo: {self.ammo}/6 | Kills: {self.kills}",
            pos=(-1.2, 0.9), scale=0.07, fg=(1, 1, 1, 1), align=0
        )

        self.crosshair = OnscreenText(
            text="+", pos=(0, 0.02), scale=0.08,
            fg=(1, 1, 1, 0.85), align=TextNode.ACenter, mayChange=False
        )

        self.taskMgr.add(self.update_game, "UpdateGame")

    def setup_inputs(self):
        self.accept("w", self.set_key, ["w", True])
        self.accept("w-up", self.set_key, ["w", False])
        self.accept("s", self.set_key, ["s", True])
        self.accept("s-up", self.set_key, ["s", False])
        self.accept("a", self.set_key, ["a", True])
        self.accept("a-up", self.set_key, ["a", False])
        self.accept("d", self.set_key, ["d", True])
        self.accept("d-up", self.set_key, ["d", False])

        self.accept("mouse1", self.shoot)
        self.accept("space", self.shoot)
        self.accept("r", self.reload)
        self.accept("escape", sys.exit)

    def set_key(self, key, value):
        self.keys[key] = value

    def setup_lighting(self):
        dlight = DirectionalLight("sun")
        dlight.setColor((1.0, 0.95, 0.85, 1))
        dnode = self.render.attachNewNode(dlight)
        dnode.setHpr(-45, -60, 0)
        self.render.setLight(dnode)

        alight = AmbientLight("ambient")
        alight.setColor((0.48, 0.48, 0.52, 1))
        anode = self.render.attachNewNode(alight)
        self.render.setLight(anode)

        distance_fog = Fog("DistanceFog")
        distance_fog.setColor(0.42, 0.65, 0.88)
        distance_fog.setLinearRange(650.0, 1150.0)
        self.render.setFog(distance_fog)

    def load_and_prep_model(self, path, fallback_color, target_size):
        container = self.render.attachNewNode("template_container")
        try:
            model = self.loader.loadModel(path)
            model.reparentTo(container)
            bounds_min, bounds_max = model.getTightBounds()
            if bounds_min and bounds_max:
                size = bounds_max - bounds_min
                max_dim = max(size.x, size.y, size.z)
                if max_dim > 0:
                    model.setScale(target_size / max_dim)
                b_min, _ = model.getTightBounds()
                model.setZ(-b_min.z)
            container.detachNode()
            return container
        except Exception as err:
            container.removeNode()
            raise err

    def create_procedural_mountain(self, key_name):
        container = self.render.attachNewNode("procedural_mountain")
        base = self.loader.loadModel("box")
        base.reparentTo(container)
        base.setScale(120, 120, 180)
        base.setPos(-60, -60, 0)
        base.setColor(0.38, 0.32, 0.26, 1)

        peak = self.loader.loadModel("box")
        peak.reparentTo(container)
        peak.setScale(70, 70, 120)
        peak.setPos(-35, -35, 120)
        peak.setHpr(45, 15, 15)
        peak.setColor(0.48, 0.42, 0.36, 1)

        container.detachNode()
        self.templates[key_name] = container
        self.valid_mountains.append(key_name)

    def preload_templates(self):
        # 1. Grass
        try:
            self.templates["grass"] = self.load_and_prep_model("assets/grass.glb", (0.2, 0.5, 0.15, 1), 2.5)
        except Exception:
            container = self.render.attachNewNode("template_container")
            fallback = self.loader.loadModel("box")
            fallback.reparentTo(container)
            fallback.setScale(0.8, 0.8, 1.2)
            fallback.setColor(0.2, 0.55, 0.15, 1)
            container.detachNode()
            self.templates["grass"] = container

        # 2. Trees (Tree 1 Excluded)
        self.valid_trees = []
        for i in range(2, 7):
            path = f"assets/tree{i}.glb"
            try:
                template = self.load_and_prep_model(path, (0.15, 0.4, 0.15, 1), 12.0)
                self.templates[f"tree{i}"] = template
                self.valid_trees.append(f"tree{i}")
            except Exception:
                pass

        if not self.valid_trees:
            container = self.render.attachNewNode("template_container")
            fallback = self.loader.loadModel("box")
            fallback.reparentTo(container)
            fallback.setScale(1.2, 1.2, 12.0)
            fallback.setColor(0.15, 0.4, 0.15, 1)
            container.detachNode()
            self.templates["fallback_tree"] = container
            self.valid_trees.append("fallback_tree")

        # 3. Mountains (Mountain 3 Excluded)
        self.valid_mountains = []
        mountain_files = [
            ("mountain1", "assets/mountain1.glb"),
            ("mountain", "assets/mountain.glb")
        ]

        for key, path in mountain_files:
            try:
                template = self.load_and_prep_model(path, (0.32, 0.28, 0.24, 1), 160.0)
                self.templates[key] = template
                self.valid_mountains.append(key)
            except Exception:
                pass

        if not self.valid_mountains:
            self.create_procedural_mountain("proc_mountain1")
            self.create_procedural_mountain("proc_mountain2")

        # 4. Houses
        for i in range(1, 8):
            try:
                self.templates[f"house{i}"] = self.load_and_prep_model(f"assets/house{i}.glb", (0.42, 0.28, 0.16, 1), 8.0)
            except Exception:
                pass

        # 5. Bandits (Bandit 4 Excluded)
        for i in [1, 2, 3, 5]:
            try:
                self.templates[f"bandit{i}"] = self.load_and_prep_model(f"assets/bandit{i}.glb", (0.8, 0.1, 0.1, 1), 2.4)
            except Exception:
                pass

        # 6. Civilian NPCs (NPC 8 Excluded)
        for i in range(1, 8):
            try:
                self.templates[f"npc{i}"] = self.load_and_prep_model(f"assets/npc{i}.glb", (0.2, 0.55, 0.3, 1), 2.2)
            except Exception:
                pass

    def setup_sky(self):
        self.sky = self.render.attachNewNode("sky_root")
        sky_loaded = False

        try:
            sky_model = self.loader.loadModel("assets/sky.glb")
            sky_model.reparentTo(self.sky)
            sky_model.setScale(1200.0)
            sky_model.setTwoSided(True)
            sky_model.setPos(0, 0, -80)
            sky_loaded = True
        except Exception:
            sky_loaded = False

        if not sky_loaded:
            sky_box = self.loader.loadModel("box")
            sky_box.setScale(2000, 2000, 1000)
            sky_box.setPos(-1000, -1000, -250)
            sky_box.setColor(0.42, 0.65, 0.88, 1)
            sky_box.setTwoSided(True)
            sky_box.reparentTo(self.sky)

        self.sky.setLightOff(1)
        self.sky.setBin("background", 0)
        self.sky.setDepthWrite(False)

    def setup_environment(self):
        self.setup_sky()

        # Ground
        cm = CardMaker("soil_ground")
        cm.setFrame(-800, 800, -800, 800)
        ground_mesh = self.render.attachNewNode(cm.generate())
        ground_mesh.setP(-90)
        ground_mesh.setColor(0.22, 0.14, 0.07, 1, 1)

        # Road
        road_cm = CardMaker("soil_road")
        road_cm.setFrame(-300, 300, -20, 20)
        road_mesh = self.render.attachNewNode(road_cm.generate())
        road_mesh.setP(-90)
        road_mesh.setPos(0, 10, 0.02)
        road_mesh.setColor(0.38, 0.26, 0.16, 1, 1)

        # River
        river_cm = CardMaker("river")
        river_cm.setFrame(-800, 800, -20, 20)
        river_mesh = self.render.attachNewNode(river_cm.generate())
        river_mesh.setP(-90)
        river_mesh.setPos(0, 120, 0.05)
        river_mesh.setColor(0.12, 0.42, 0.72, 0.9, 1)

        # Grass Spawning
        grass_root = self.render.attachNewNode("grass_root")
        grass_spawned = 0
        while grass_spawned < 300:
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(10, 320)
            gx = dist * math.cos(angle)
            gy = dist * math.sin(angle)

            if abs(gy - 10) < 18 and abs(gx) < 200:
                continue
            if abs(gy - 120) < 22:
                continue

            g = self.templates["grass"].copyTo(grass_root)
            g.setPos(gx, gy, 0)
            g.setScale(random.uniform(0.8, 1.4))
            g.setH(random.uniform(0, 360))
            grass_spawned += 1

        grass_root.flattenStrong()

        # Surrounding Mountain Ring
        mountains_root = self.render.attachNewNode("mountains_root")
        num_mountains = 16

        for i in range(num_mountains):
            angle_rad = (2 * math.pi / num_mountains) * i
            dist = 450.0
            mx = dist * math.cos(angle_rad)
            my = dist * math.sin(angle_rad)

            if abs(my - 120) > 50:
                selected_model = random.choice(self.valid_mountains)
                m = self.templates[selected_model].copyTo(mountains_root)
                m.setPos(mx, my, -5.0)
                m.setScale(random.uniform(1.3, 1.9))
                m.setH(random.uniform(0, 360))

        mountains_root.flattenMedium()

        # Town Setup
        houses_root = self.render.attachNewNode("houses_root")
        valid_house_keys = [k for k in self.templates if k.startswith("house")]
        for x in range(-180, 180, 30):
            if valid_house_keys:
                h1 = self.templates[random.choice(valid_house_keys)].copyTo(houses_root)
                h1.setPos(x, 40, 0)
                h1.setH(0)

                h2 = self.templates[random.choice(valid_house_keys)].copyTo(houses_root)
                h2.setPos(x, -20, 0)
                h2.setH(180)

        houses_root.flattenMedium()

        # Forests
        forest_root = self.render.attachNewNode("forest_root")

        # City Outskirts Trees
        city_trees_spawned = 0
        while city_trees_spawned < 150:
            cx = random.uniform(-210, 210)
            cy = random.choice([random.uniform(50, 110), random.uniform(-90, -30)])
            if abs(cy - 120) < 20:
                continue

            t = self.templates[random.choice(self.valid_trees)].copyTo(forest_root)
            t.setPos(cx, cy, 0)
            t.setScale(random.uniform(0.8, 1.3))
            t.setH(random.uniform(0, 360))
            city_trees_spawned += 1

        # Mountain Forest Belt
        mountain_trees_spawned = 0
        while mountain_trees_spawned < 350:
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(310, 430)
            tx = dist * math.cos(angle)
            ty = dist * math.sin(angle)

            if abs(ty - 120) < 25:
                continue

            t = self.templates[random.choice(self.valid_trees)].copyTo(forest_root)
            t.setPos(tx, ty, 0)
            t.setScale(random.uniform(0.9, 1.5))
            t.setH(random.uniform(0, 360))
            mountain_trees_spawned += 1

        forest_root.flattenMedium()

        # Civilian NPCs
        valid_npc_keys = [k for k in self.templates if k.startswith("npc")]
        self.civilians = []
        if valid_npc_keys:
            for _ in range(45):
                cx = random.uniform(-180, 180)
                cy = random.uniform(-28, 48)
                npc = self.templates[random.choice(valid_npc_keys)].copyTo(self.render)
                npc.setPos(cx, cy, 0)
                npc.setH(random.uniform(0, 360))
                self.civilians.append(npc)

        # Hostile Bandits
        valid_bandit_keys = [k for k in self.templates if k.startswith("bandit")]
        self.bandits = []
        if valid_bandit_keys:
            for _ in range(30):
                bx = random.uniform(-280, 280)
                by = random.uniform(-280, 280)
                if (abs(bx) > 120 or abs(by) > 50) and math.hypot(bx, by) > 40:
                    b = self.templates[random.choice(valid_bandit_keys)].copyTo(self.render)
                    b.setPos(bx, by, 0)
                    b.setH(random.uniform(0, 360))
                    self.bandits.append(b)

    def setup_character(self):
        self.player = self.render.attachNewNode("PlayerContainer")
        self.player.setPos(0, 0, 0)

        try:
            self.horse = self.load_and_prep_model("assets/horse.glb", (0.35, 0.2, 0.1, 1), 3.5)
            self.horse.reparentTo(self.player)
            self.horse.setH(180)
        except Exception:
            pass

        try:
            self.rider = self.load_and_prep_model("assets/cowboy.glb", (0.2, 0.3, 0.6, 1), 2.0)
            self.rider.reparentTo(self.player)
            self.rider.setPos(0, 0.0, 0.95)
            self.rider.setH(180)
        except Exception:
            pass

        self.disableMouse()
        self.camera.reparentTo(self.player)
        self.camera.setPos(0.8, -8.0, 3.2)
        self.camera.setP(-2)

    def shoot(self):
        if self.ammo <= 0 or self.is_reloading:
            return

        self.ammo -= 1
        self.ui_text.setText(f"Ammo: {self.ammo}/6 | Kills: {self.kills}")

        px, py, _ = self.player.getPos()
        heading = self.player.getH()

        for bandit in list(self.bandits):
            bx, by, _ = bandit.getPos()
            dist = math.hypot(bx - px, by - py)

            angle_to_b = math.degrees(math.atan2(by - py, bx - px)) - heading
            normalized_angle = (angle_to_b + 180) % 360 - 180

            if dist < 60 and abs(normalized_angle - 90) < 25:
                bandit.removeNode()
                self.bandits.remove(bandit)
                self.kills += 1
                self.ui_text.setText(f"Ammo: {self.ammo}/6 | Kills: {self.kills}")
                break

    def reload(self):
        if not self.is_reloading and self.ammo < 6:
            self.is_reloading = True
            self.ui_text.setText("RELOADING...")
            self.taskMgr.doMethodLater(1.5, self.finish_reload, "FinishReload")

    def finish_reload(self, task):
        self.ammo = 6
        self.is_reloading = False
        self.ui_text.setText(f"Ammo: {self.ammo}/6 | Kills: {self.kills}")
        return task.done

    def update_game(self, task):
        dt = globalClock.getDt()
        speed = 18.0 * dt
        rot_speed = 70.0 * dt

        if self.keys["a"]:
            self.player.setH(self.player.getH() + rot_speed)
        if self.keys["d"]:
            self.player.setH(self.player.getH() - rot_speed)
        if self.keys["w"]:
            self.player.setY(self.player, speed)
        if self.keys["s"]:
            self.player.setY(self.player, -speed * 0.5)

        if hasattr(self, 'sky') and self.sky:
            self.sky.setPos(self.player.getPos())

        return task.cont


if __name__ == "__main__":
    game = RedWest3D()
    game.run()