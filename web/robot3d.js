// 3D view of recorded simulator states. Nothing here simulates or invents motion: every pose comes from a stored
// episode trace (robot x, y, heading and mover positions per 0.1 s step). The lidar rays are recomputed from each
// recorded pose with the simulator's own geometry (ew/env.py _ray_ranges): 12 rays, CCW from heading, walls plus
// circular obstacles, range measured from the robot's edge and clipped to 4 m. Wheel spin follows the recorded
// motion (differential drive). The pedestrian's legs swing in proportion to the distance it actually moved.
import * as THREE from "./vendor/three.module.min.js";

const WORLD = 10, R_ROBOT = 0.2, RAY_MAX = 4, N_RAYS = 12, WHEEL_R = 0.05, TRACK = 0.34, LIDAR_H = 0.17;
const css = (n, fb) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || fb;
// sim (x, y) -> three (x, 0, -y), centred on the arena; heading th -> rotation.y = th
const P = (x, y, h = 0) => new THREE.Vector3(x - WORLD / 2, h, -(y - WORLD / 2));

export function webglOK() {
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; }
}

export function rays(pose, circles) {
  const [x, y, th] = pose, out = [];
  for (let i = 0; i < N_RAYS; i++) {
    const a = th + (i * 2 * Math.PI) / N_RAYS, dx = Math.cos(a), dy = Math.sin(a);
    const tx = dx > 0 ? (WORLD - x) / dx : dx < 0 ? -x / dx : Infinity;
    const ty = dy > 0 ? (WORLD - y) / dy : dy < 0 ? -y / dy : Infinity;
    let hit = Math.min(tx, ty);
    for (const [ox0, oy0, r] of circles) {
      const ox = ox0 - x, oy = oy0 - y, b = ox * dx + oy * dy, cc = ox * ox + oy * oy - r * r, disc = b * b - cc;
      let t = Infinity;
      if (disc >= 0 && b - Math.sqrt(disc) > 0) t = b - Math.sqrt(disc); else if (cc <= 0) t = 0;
      hit = Math.min(hit, t);
    }
    out.push({ a, free: Math.min(Math.max(hit - R_ROBOT, 0), RAY_MAX) });
  }
  return out;
}

function mat(color, o = {}) { return new THREE.MeshStandardMaterial({ color, roughness: .55, metalness: .05, ...o }); }

function buildRobot(body) {
  const g = new THREE.Group();
  const shadow = { castShadow: true, receiveShadow: true };
  const add = (geo, m, pos, rot) => { const x = new THREE.Mesh(geo, m); Object.assign(x, shadow); x.position.set(...pos); if (rot) x.rotation.set(...rot); g.add(x); return x; };
  add(new THREE.CylinderGeometry(R_ROBOT, R_ROBOT, .09, 48), mat(body), [0, .075, 0]);
  add(new THREE.CylinderGeometry(R_ROBOT * .93, R_ROBOT * .93, .014, 48), mat("#2a2f36", { roughness: .4 }), [0, .127, 0]);
  add(new THREE.CylinderGeometry(R_ROBOT + .004, R_ROBOT + .004, .02, 48), mat("#1b2026"), [0, .04, 0]);
  // lidar puck
  const lidar = new THREE.Group(); lidar.position.set(0, .15, 0); g.add(lidar);
  const lm = new THREE.Mesh(new THREE.CylinderGeometry(.055, .06, .045, 32), mat("#15181c", { roughness: .3, metalness: .3 })); lm.castShadow = true; lidar.add(lm);
  const lens = new THREE.Mesh(new THREE.BoxGeometry(.03, .016, .1), mat("#ff7a1a", { emissive: "#ff5a00", emissiveIntensity: .6 })); lens.position.set(.045, .004, 0); lidar.add(lens);
  // front light, so heading reads at a glance (+x is forward)
  add(new THREE.BoxGeometry(.03, .025, .12), mat("#fff3d6", { emissive: "#ffd28a", emissiveIntensity: .9 }), [R_ROBOT - .01, .085, 0]);
  // wheels: local -z is the robot's left (sim +y maps to three -z), +z its right
  const wheels = [-1, 1].map((side) => {
    const w = new THREE.Group(); w.position.set(0, WHEEL_R, side * (TRACK / 2)); g.add(w);
    const tyre = new THREE.Mesh(new THREE.CylinderGeometry(WHEEL_R, WHEEL_R, .028, 28), mat("#1d1f22", { roughness: .9 }));
    tyre.rotation.x = Math.PI / 2; tyre.castShadow = true; w.add(tyre);
    const hub = new THREE.Mesh(new THREE.BoxGeometry(.07, .012, .03), mat("#c9ccd0", { metalness: .6, roughness: .3 }));
    hub.position.z = side * .006; w.add(hub);
    return w;
  });
  add(new THREE.SphereGeometry(.022, 16, 12), mat("#9aa0a6", { metalness: .5 }), [-.15, .022, 0]);
  return { g, lidar, wheels };
}

function buildPerson(color) {
  const g = new THREE.Group(), skin = mat("#c99a76", { roughness: .7 }), cloth = mat(color), dark = mat("#2b2f35");
  const limb = (len, r, m) => { const p = new THREE.Group(); const x = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 12), m); x.position.y = -len / 2 - r; x.castShadow = true; p.add(x); return p; };
  const hipL = limb(.72, .065, dark), hipR = limb(.72, .065, dark);
  hipL.position.set(0, .93, .1); hipR.position.set(0, .93, -.1); g.add(hipL, hipR);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(.17, .42, 8, 16), cloth); torso.position.y = 1.2; torso.scale.z = 1.25; torso.castShadow = true; g.add(torso);
  const head = new THREE.Mesh(new THREE.SphereGeometry(.12, 20, 16), skin); head.position.y = 1.62; head.castShadow = true; g.add(head);
  const shL = limb(.5, .05, cloth), shR = limb(.5, .05, cloth);
  shL.position.set(0, 1.42, .25); shR.position.set(0, 1.42, -.25); g.add(shL, shR);
  return { g, legs: [hipL, hipR], arms: [shL, shR] };
}

export class Arena3D {
  // eps: [{ ep, body, label }], each ep = { layout, robot: [[x,y,th]...], movers: [[[x,y]...]...], outcome }
  constructor(container, eps, { fit = 1.5 } = {}) {
    this.container = container; this.eps = eps; this.k = 0; this.fit = fit;
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
    r.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.05;
    r.domElement.setAttribute("aria-hidden", "true");
    container.appendChild(r.domElement);
    const s = this.scene = new THREE.Scene();
    s.background = new THREE.Color(css("--paper", "#f4f2ec"));
    s.fog = new THREE.Fog(s.background, 18, 34);
    this.camera = new THREE.PerspectiveCamera(34, 1, .1, 100);
    this.az = -.3; this.el = .82; this.dist = 13.5;
    s.add(new THREE.HemisphereLight("#ffffff", "#b8b2a2", 1.1));
    const sun = new THREE.DirectionalLight("#fff4e0", 2.1);
    sun.position.set(-6, 12, 7); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 1, far: 30 }); sun.shadow.bias = -.0005;
    s.add(sun);
    this.buildWorld(eps[0].ep.layout);
    this.bots = eps.map(({ ep, body }) => this.buildBot(ep, body));
    // small screen-space name tags above each robot, so the 0.2 m robots read at a glance without being scaled
    eps.forEach(({ tag, body }, i) => {
      if (!tag) return;
      const t = document.createElement("span"); t.className = "tag3d"; t.textContent = tag; t.style.setProperty("--c", body);
      container.appendChild(t); this.bots[i].tag = t;
    });
    const longest = eps.reduce((a, b) => (b.ep.movers.length > a.ep.movers.length ? b : a)).ep;
    this.moverTrack = longest.movers;
    this.people = longest.layout.movers.map((m) => { const p = buildPerson(css("--ped", "#2b4c7e")); s.add(p.g); return { ...p, r: m[4] }; });
    this.pedDist = this.moverTrack.map(() => 0);
    for (let t = 1; t < this.moverTrack.length; t++) this.pedDist[t] = this.pedDist[t - 1] + Math.hypot(this.moverTrack[t][0][0] - this.moverTrack[t - 1][0][0], this.moverTrack[t][0][1] - this.moverTrack[t - 1][0][1]);
    this.discs = this.people.map((p) => { const d = new THREE.Mesh(new THREE.RingGeometry(p.r - .03, p.r, 48), new THREE.MeshBasicMaterial({ color: css("--ped", "#2b4c7e"), transparent: true, opacity: .45 })); d.rotation.x = -Math.PI / 2; d.position.y = .006; s.add(d); return d; });
    this.drag();
    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(container);
    this.resize();
    this.setStep(0);
  }

  buildWorld(layout) {
    const s = this.scene;
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(WORLD, WORLD), mat(css("--surface", "#fbfaf7"), { roughness: .95 }));
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; s.add(floor);
    const outer = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), mat(css("--alt", "#eceae2"), { roughness: 1 }));
    outer.rotation.x = -Math.PI / 2; outer.position.y = -.01; outer.receiveShadow = true; s.add(outer);
    const grid = new THREE.GridHelper(WORLD, WORLD, css("--line", "#d6d2c6"), css("--line", "#d6d2c6")); grid.position.y = .002; s.add(grid);
    const wallM = mat("#c7c2b4", { roughness: .8 });
    for (const [w, d, x, z] of [[WORLD + .2, .1, 0, -WORLD / 2 - .05], [WORLD + .2, .1, 0, WORLD / 2 + .05], [.1, WORLD, -WORLD / 2 - .05, 0], [.1, WORLD, WORLD / 2 + .05, 0]]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, .18, d), wallM); m.position.set(x, .09, z); m.castShadow = m.receiveShadow = true; s.add(m);
    }
    const band = mat("#e0a100", { roughness: .6 }), conc = mat("#9aa0a6", { roughness: .85 }), top = mat("#7d838a", { roughness: .8 });
    for (const [x, y, r] of layout.statics) {
      const g = new THREE.Group(); g.position.copy(P(x, y));
      const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, .55, 40), conc); c.position.y = .275;
      const b = new THREE.Mesh(new THREE.CylinderGeometry(r + .003, r + .003, .07, 40), band); b.position.y = .42;
      const t = new THREE.Mesh(new THREE.CylinderGeometry(r * .96, r, .04, 40), top); t.position.y = .57;
      for (const m of [c, b, t]) { m.castShadow = m.receiveShadow = true; g.add(m); }
      s.add(g);
    }
    const [gx, gy] = layout.goal, ok = css("--ok", "#2f6b2f");
    const ring = new THREE.Mesh(new THREE.RingGeometry(.22, .3, 48), new THREE.MeshBasicMaterial({ color: ok })); ring.rotation.x = -Math.PI / 2; ring.position.copy(P(gx, gy, .006)); s.add(ring);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(.012, .012, .9, 8), mat("#4a4f55")); pole.position.copy(P(gx, gy, .45)); pole.castShadow = true; s.add(pole);
    const flag = new THREE.Mesh(new THREE.PlaneGeometry(.3, .18), new THREE.MeshStandardMaterial({ color: ok, side: THREE.DoubleSide })); flag.position.copy(P(gx, gy, .8)); flag.position.x += .15; flag.castShadow = true; s.add(flag);
    this.goalRing = ring;
  }

  buildBot(ep, body) {
    const bot = buildRobot(body); this.scene.add(bot.g);
    const trailG = new THREE.BufferGeometry().setFromPoints(ep.robot.map((p) => P(p[0], p[1], .012)));
    const trail = new THREE.Line(trailG, new THREE.LineBasicMaterial({ color: body, transparent: true, opacity: .9 }));
    this.scene.add(trail);
    const rayG = new THREE.BufferGeometry(); rayG.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N_RAYS * 6), 3));
    rayG.setAttribute("color", new THREE.BufferAttribute(new Float32Array(N_RAYS * 6), 3));
    const rayL = new THREE.LineSegments(rayG, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: .8 }));
    this.scene.add(rayL);
    const hitG = new THREE.BufferGeometry(); hitG.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N_RAYS * 3), 3));
    const hits = new THREE.Points(hitG, new THREE.PointsMaterial({ color: "#d9480f", size: .09 })); this.scene.add(hits);
    const mark = new THREE.Mesh(new THREE.RingGeometry(.26, .36, 48), new THREE.MeshBasicMaterial({ color: ep.outcome === "collision" ? css("--bad", "#b42318") : css("--ok", "#2f6b2f"), transparent: true, opacity: .9, side: THREE.DoubleSide }));
    mark.rotation.x = -Math.PI / 2; mark.visible = false; this.scene.add(mark);
    // wheel angle per step from the recorded motion: signed forward distance and heading change
    const wl = [0], wr = [0];
    for (let t = 1; t < ep.robot.length; t++) {
      const [x0, y0, a0] = ep.robot[t - 1], [x1, y1, a1] = ep.robot[t];
      const fwd = (x1 - x0) * Math.cos(a0) + (y1 - y0) * Math.sin(a0);
      let da = a1 - a0; da = Math.atan2(Math.sin(da), Math.cos(da));
      wl.push(wl[t - 1] + (fwd - (da * TRACK) / 2) / WHEEL_R); wr.push(wr[t - 1] + (fwd + (da * TRACK) / 2) / WHEEL_R);
    }
    return { ep, bot, trail, trailG, rayL, rayG, hits, hitG, mark, wl, wr, tag: null };
  }

  setStep(k) {
    this.k = k;
    const tm = Math.min(k, this.moverTrack.length - 1);
    this.moverTrack[tm].forEach((m, i) => {
      const p = this.people[i]; if (!p) return;
      p.g.position.copy(P(m[0], m[1])); this.discs[i].position.set(p.g.position.x, .006, p.g.position.z);
      const prev = this.moverTrack[Math.max(tm - 1, 0)][i], next = this.moverTrack[Math.min(tm + 1, this.moverTrack.length - 1)][i];
      const vx = next[0] - prev[0], vy = next[1] - prev[1];
      if (Math.hypot(vx, vy) > 1e-6) p.g.rotation.y = Math.atan2(vy, vx);
      const ph = (this.pedDist[tm] / .55) * Math.PI, sw = Math.sin(ph) * .45;
      p.legs[0].rotation.z = sw; p.legs[1].rotation.z = -sw; p.arms[0].rotation.z = -sw * .7; p.arms[1].rotation.z = sw * .7;
    });
    for (const b of this.bots) {
      const n = b.ep.robot.length - 1, t = Math.min(k, n), pose = b.ep.robot[t];
      b.bot.g.position.copy(P(pose[0], pose[1])); b.bot.g.rotation.y = pose[2];
      b.bot.wheels[0].rotation.z = -b.wl[t]; b.bot.wheels[1].rotation.z = -b.wr[t];
      b.bot.lidar.rotation.y = t * .9;
      b.trailG.setDrawRange(0, t + 1);
      const movers = b.ep.movers[t].map((m, i) => [m[0], m[1], b.ep.layout.movers[i][4]]);
      const rs = rays(pose, [...b.ep.layout.statics, ...movers]);
      const pos = b.rayG.attributes.position.array, col = b.rayG.attributes.color.array, hp = b.hitG.attributes.position.array;
      rs.forEach((r, i) => {
        const dx = Math.cos(r.a), dy = Math.sin(r.a);
        const a = P(pose[0] + dx * R_ROBOT, pose[1] + dy * R_ROBOT, LIDAR_H), e = P(pose[0] + dx * (R_ROBOT + r.free), pose[1] + dy * (R_ROBOT + r.free), LIDAR_H);
        pos.set([a.x, a.y, a.z, e.x, e.y, e.z], i * 6);
        const c = new THREE.Color(r.free >= RAY_MAX ? "#c9c4b6" : r.free < .6 ? "#d92d20" : r.free < 1.5 ? "#f08c00" : "#ff7a1a");
        col.set([c.r, c.g, c.b, c.r, c.g, c.b], i * 6);
        if (r.free < RAY_MAX) hp.set([e.x, e.y, e.z], i * 3); else hp.set([0, -5, 0], i * 3);
      });
      b.rayG.attributes.position.needsUpdate = b.rayG.attributes.color.needsUpdate = b.hitG.attributes.position.needsUpdate = true;
      b.rayL.visible = b.hits.visible = t < n || b.ep.outcome !== "success";
      b.mark.visible = t === n; b.mark.position.set(b.bot.g.position.x, .008, b.bot.g.position.z);
    }
    this.render();
  }

  drag() {
    const el = this.renderer.domElement; let sx = 0, sy = 0, a0 = 0, e0 = 0, on = false;
    el.style.touchAction = "pan-y"; el.style.cursor = "grab";
    el.addEventListener("pointerdown", (e) => { on = true; sx = e.clientX; sy = e.clientY; a0 = this.az; e0 = this.el; el.setPointerCapture(e.pointerId); el.style.cursor = "grabbing"; });
    el.addEventListener("pointermove", (e) => {
      if (!on) return;
      this.az = Math.max(-1.3, Math.min(1.3, a0 - (e.clientX - sx) * .006));
      this.el = Math.max(.35, Math.min(1.35, e0 + (e.clientY - sy) * .004));
      this.place(); this.render();
    });
    const end = () => { on = false; el.style.cursor = "grab"; };
    el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
  }

  place() {
    const c = this.camera, d = this.dist;
    c.position.set(Math.sin(this.az) * Math.cos(this.el) * d, Math.sin(this.el) * d, Math.cos(this.az) * Math.cos(this.el) * d);
    c.lookAt(0, -.6, -.3);
  }

  resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.dist = 13.5 * Math.max(1, this.fit / (w / h));
    this.camera.updateProjectionMatrix(); this.place(); this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
    const w = this.container.clientWidth, h = this.container.clientHeight, v = new THREE.Vector3();
    for (const b of this.bots) {
      if (!b.tag) continue;
      v.copy(b.bot.g.position); v.y = .5; v.project(this.camera);
      b.tag.style.transform = `translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h}px) translate(-50%, -100%)`;
    }
  }

  dispose() { this.ro.disconnect(); this.renderer.dispose(); this.renderer.domElement.remove(); }
}
