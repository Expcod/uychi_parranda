/** @odoo-module **/
/**
 * 3D sahna — korxonani haqiqiy manzara ko'rinishida ko'rsatadi.
 *
 * Nega 3D: rahbar uchun jadvaldagi 40 qator o'rniga bitta manzara — qaysi bino
 * (bo'lim, partiya, ombor) katta, qaysi biri qizil — bir qarashda ko'rinadi,
 * binoni bosib esa tafsilotga o'tiladi. Mijozga taqdimotda ham tushuntirish oson.
 *
 * Manzara: osmon va tuman, o't qoplami, asfalt yo'llar (ular bo'ylab yuk
 * mashinalari yuradi), daraxtlar, atrofdagi ekin dalalari. Har bo'limning o'z
 * binosi bor: parrandaxona, yem zavodi, inkubatoriya, so'yish sexi, do'kon,
 * ofis, ombor, dala, avtobaza. Holat bino ostidagi maydon hoshiyasi va
 * chiroq-mayoq rangida; og'ish bo'lsa mayoq miltillaydi va yerda to'lqin tarqaladi.
 *
 * three.js faqat sahna birinchi marta ochilganda yuklanadi (`loadJS`), umumiy
 * asset bundle'ga qo'shilmaydi — Odoo'ning boshqa sahifalari og'irlashmaydi.
 * Barcha teksturalar canvas'da chiziladi — tashqi rasm fayllari yo'q.
 *
 * Odoo «Dark» temasida sahna tunga o'tadi: to'q osmon, oy nuri, yonib turgan
 * derazalar va mashina chiroqlari (tema `color_scheme` cookie'sidan olinadi).
 *
 * Ikki rejim:
 *   chain — `node.pos = [x, z]` bilan berilgan zanjir + yo'llar;
 *   farm  — `node.group` bo'yicha qatorlarga avtomatik joylashtiriladi.
 */
import { Component, onMounted, onWillUnmount, toRaw, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";

const THREE_URL = "/agronova_dashboard/static/lib/three/three.min.js";

const STATUS = {
    ok: 0x22c55e,
    bad: 0xef4444,
    idle: 0x94a3b8,
    neutral: 0x3b82f6,
};

const C = {
    fog: 0xdfe8ea,
    concrete: 0xcfd2cc,
    asphalt: 0xffffff, // rang teksturada
    wall: 0xf2efe6,
    wallWarm: 0xe7dcc4,
    roofRed: 0x9a3d32,
    roofGreen: 0x3f6b58,
    roofGrey: 0x8d969e,
    metal: 0xc9d0d6,
    glass: 0x27445e,
    wood: 0xa8743f,
    woodLight: 0xc99a5f,
    trim: 0x56606b,
    tire: 0x1e2226,
    yellow: 0xe0a83a,
    brand: 0x2563eb,
};

/** Takrorlanadigan tasodifiy sonlar — sahna har ochilganda bir xil ko'rinsin. */
function seeded(seed) {
    let a = seed >>> 0;
    return () => {
        a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

export class Scene3D extends Component {
    static template = "agronova_dashboard.Scene3D";
    static props = {
        scene: Object,
        onPick: { type: Function, optional: true },
    };

    setup() {
        this.hostRef = useRef("host");
        this.labelsRef = useRef("labels");
        this.state = useState({
            ready: false,
            failed: false,
            autoRotate: true,
            hover: null,
        });
        this._disposables = [];
        this._pickables = [];
        this._pulses = [];
        this._beacons = [];
        this._vehicles = [];
        this._spinners = [];
        this._smoke = [];
        this._labels = [];
        this._nodeGroups = [];
        this._nodeLabels = [];
        this._mc = new Map();
        this._tx = {};
        // Reaktiv proksi emas, oddiy obyekt: THREE obyektlari proksiga o'ralmasin.
        this.data = toRaw(this.props.scene);
        this.night = cookie.get("color_scheme") === "dark";
        onMounted(() => this._init());
        onWillUnmount(() => this._dispose());
    }

    // ------------------------------------------------------------------
    // Ishga tushirish
    // ------------------------------------------------------------------
    async _init() {
        try {
            if (!window.THREE) {
                await loadJS(THREE_URL);
            }
        } catch {
            this.state.failed = true;
            return;
        }
        if (this._destroyed || !this.hostRef.el) {
            return;
        }
        const THREE = window.THREE;
        this.THREE = THREE;
        try {
            this.renderer = new THREE.WebGLRenderer({ antialias: true });
        } catch {
            // WebGL o'chirilgan yoki qo'llab-quvvatlanmaydi — 2D ro'yxat ko'rinadi.
            this.state.failed = true;
            return;
        }
        const host = this.hostRef.el;
        const renderer = this.renderer;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.outputEncoding = THREE.sRGBEncoding;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = this.night ? 1.0 : 0.98;
        host.appendChild(renderer.domElement);

        this.scene3 = new THREE.Scene();
        this.scene3.background = this._skyTexture();
        this.scene3.fog = new THREE.Fog(this.night ? 0x12233d : C.fog, 40, 140);
        this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 800);
        this.clock = new THREE.Clock();

        const bounds = this._buildWorld();
        this._buildLights(bounds);
        this._setupOrbit(bounds);
        this._bindEvents();
        this._resize();

        this._resizeObserver = new ResizeObserver(() => this._resize());
        this._resizeObserver.observe(host);
        // Ko'rinmay qolganda (pastga aylantirilganda) kadr chizilmaydi — CPU tejaladi.
        this._visible = true;
        this._io = new IntersectionObserver((entries) => {
            this._visible = entries.some((e) => e.isIntersecting);
        });
        this._io.observe(host);

        this.state.ready = true;
        this._loop();
    }

    _buildLights(bounds) {
        const THREE = this.THREE;
        const night = this.night;
        this.scene3.add(night
            ? new THREE.HemisphereLight(0x5d7fbf, 0x0c1220, 0.32)
            : new THREE.HemisphereLight(0xdcecff, 0x5d6b45, 0.75));
        // Kunduzi — iliq quyosh, tunda — sovuq oy nuri.
        const sun = new THREE.DirectionalLight(night ? 0xa9c4ff : 0xfff0d8, night ? 0.42 : 1.55);
        const s = bounds.size * 0.62;
        sun.position.set(bounds.cx + s * 0.8, s * 1.4, bounds.cz + s * 0.55);
        sun.target.position.set(bounds.cx, 0, bounds.cz);
        sun.castShadow = true;
        sun.shadow.mapSize.set(2048, 2048);
        sun.shadow.bias = -0.0004;
        sun.shadow.normalBias = 0.02;
        Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 1, far: s * 4 });
        this.scene3.add(sun, sun.target);
    }

    // ------------------------------------------------------------------
    // Teksturalar (canvas) va materiallar
    // ------------------------------------------------------------------
    _canvasTex(w, h, draw, rx = 1, ry = 1) {
        const THREE = this.THREE;
        const c = document.createElement("canvas");
        c.width = w;
        c.height = h;
        draw(c.getContext("2d"), w, h);
        const t = new THREE.CanvasTexture(c);
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.repeat.set(rx, ry);
        t.encoding = THREE.sRGBEncoding;
        t.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
        this._disposables.push(t);
        return t;
    }

    _skyTexture() {
        const t = this._canvasTex(4, 256, (g, w, h) => {
            const grad = g.createLinearGradient(0, 0, 0, h);
            const stops = this.night
                ? ["#050b18", "#0b1a33", "#112241", "#12233d"]
                : ["#4f8fd0", "#9cc6ec", "#d7e6ee", "#dfe8ea"];
            grad.addColorStop(0, stops[0]);
            grad.addColorStop(0.45, stops[1]);
            grad.addColorStop(0.8, stops[2]);
            grad.addColorStop(1, stops[3]);
            g.fillStyle = grad;
            g.fillRect(0, 0, w, h);
        });
        t.wrapS = t.wrapT = this.THREE.ClampToEdgeWrapping;
        return t;
    }

    /** Nomlangan teksturalar — bir marta chiziladi, keyin qayta ishlatiladi. */
    _t(name) {
        if (this._tx[name]) {
            return this._tx[name];
        }
        const rnd = seeded(name.length * 977);
        const noise = (g, w, h, n, colors, size = 2) => {
            for (let i = 0; i < n; i++) {
                g.fillStyle = colors[Math.floor(rnd() * colors.length)];
                const s = 1 + rnd() * size;
                g.fillRect(rnd() * w, rnd() * h, s, s);
            }
        };
        const makers = {
            grass: () => this._canvasTex(256, 256, (g, w, h) => {
                g.fillStyle = "#6f9a49";
                g.fillRect(0, 0, w, h);
                for (let i = 0; i < 18; i++) {
                    const x = rnd() * w, y = rnd() * h, r = 20 + rnd() * 50;
                    const rg = g.createRadialGradient(x, y, 0, x, y, r);
                    rg.addColorStop(0, rnd() > 0.5 ? "rgba(140,175,80,0.35)" : "rgba(80,120,50,0.3)");
                    rg.addColorStop(1, "rgba(0,0,0,0)");
                    g.fillStyle = rg;
                    g.fillRect(x - r, y - r, r * 2, r * 2);
                }
                noise(g, w, h, 5000, ["#5e8a3c", "#7fae55", "#88b45e", "#668f42", "#93ba69", "#577f37"]);
            }),
            road: () => this._canvasTex(64, 128, (g, w, h) => {
                g.fillStyle = "#4d5259";
                g.fillRect(0, 0, w, h);
                noise(g, w, h, 900, ["#454a50", "#575c63", "#5d6168"], 1.5);
                g.fillStyle = "#d9d6c8";
                g.fillRect(3, 0, 2, h);
                g.fillRect(w - 5, 0, 2, h);
                g.fillStyle = "#f0d264";
                g.fillRect(w / 2 - 1.5, 8, 3, h / 2 - 8);
            }),
            concrete: () => this._canvasTex(128, 128, (g, w, h) => {
                g.fillStyle = "#c9ccc6";
                g.fillRect(0, 0, w, h);
                noise(g, w, h, 2500, ["#bfc2bc", "#d3d6d0", "#b6b9b3"], 1.5);
                g.strokeStyle = "rgba(90,95,90,0.35)";
                g.lineWidth = 1;
                g.strokeRect(0.5, 0.5, w - 1, h - 1);
            }),
            corrugated: () => this._canvasTex(64, 8, (g, w) => {
                for (let x = 0; x < w; x++) {
                    const v = Math.round(205 + 50 * Math.sin((x / w) * Math.PI * 2 * 8));
                    g.fillStyle = `rgb(${v},${v},${v})`;
                    g.fillRect(x, 0, 1, 8);
                }
            }, 6, 1),
            ribs: () => this._canvasTex(8, 64, (g, w, h) => {
                for (let y = 0; y < h; y++) {
                    const v = Math.round(215 + 40 * Math.sin((y / h) * Math.PI * 2 * 6));
                    g.fillStyle = `rgb(${v},${v},${v})`;
                    g.fillRect(0, y, w, 1);
                }
                g.fillStyle = "rgba(0,0,0,0.12)";
                g.fillRect(0, 0, 1, h);
            }, 10, 3),
            siding: () => this._canvasTex(8, 64, (g, w, h) => {
                g.fillStyle = "#ffffff";
                g.fillRect(0, 0, w, h);
                g.fillStyle = "rgba(0,0,0,0.07)";
                for (let y = 0; y < h; y += 8) {
                    g.fillRect(0, y, w, 1);
                }
            }, 1, 3),
            soil: () => this._canvasTex(128, 128, (g, w, h) => {
                g.fillStyle = "#7b5636";
                g.fillRect(0, 0, w, h);
                for (let y = 0; y < h; y += 8) {
                    g.fillStyle = "#664529";
                    g.fillRect(0, y, w, 3);
                }
                noise(g, w, h, 1600, ["#8a6340", "#5f412a", "#93704b"], 1.5);
            }, 2, 2),
            crops: () => this._canvasTex(64, 64, (g, w, h) => {
                g.fillStyle = "#ffffff";
                g.fillRect(0, 0, w, h);
                for (let y = 0; y < h; y += 8) {
                    g.fillStyle = "rgba(0,0,0,0.22)";
                    g.fillRect(0, y, w, 3);
                }
                noise(g, w, h, 500, ["rgba(0,0,0,0.12)", "rgba(255,255,255,0.25)"], 2);
            }, 6, 6),
            awning: () => this._canvasTex(64, 8, (g, w) => {
                for (let i = 0; i < 8; i++) {
                    g.fillStyle = i % 2 ? "#f8fafc" : "#dc4a3c";
                    g.fillRect(i * (w / 8), 0, w / 8, 8);
                }
            }),
            shutter: () => this._canvasTex(8, 64, (g, w, h) => {
                g.fillStyle = "#9aa3ab";
                g.fillRect(0, 0, w, h);
                g.fillStyle = "#7d868e";
                for (let y = 0; y < h; y += 4) {
                    g.fillRect(0, y, w, 1);
                }
            }),
            windows: () => this._canvasTex(128, 128, (g, w, h) => {
                g.fillStyle = "#e4e1d9";
                g.fillRect(0, 0, w, h);
                for (const [x, y] of [[8, 14], [72, 14], [8, 78], [72, 78]]) {
                    const lg = g.createLinearGradient(x, y, x + 48, y + 44);
                    lg.addColorStop(0, "#5d87a8");
                    lg.addColorStop(0.55, "#2c4c69");
                    lg.addColorStop(1, "#1f3850");
                    g.fillStyle = lg;
                    g.fillRect(x, y, 48, 40);
                    g.fillStyle = "rgba(255,255,255,0.18)";
                    g.fillRect(x + 2, y + 2, 14, 36);
                }
            }),
            // Tungi derazalar: faqat oynalar yonadi, devor qora (emissiveMap).
            windowsLit: () => this._canvasTex(128, 128, (g, w, h) => {
                g.fillStyle = "#000000";
                g.fillRect(0, 0, w, h);
                for (const [x, y, on] of [[8, 14, 1], [72, 14, 0.35], [8, 78, 0.7], [72, 78, 1]]) {
                    g.fillStyle = `rgba(255, 214, 150, ${on})`;
                    g.fillRect(x, y, 48, 40);
                }
            }),
        };
        this._tx[name] = makers[name]();
        return this._tx[name];
    }

    /** Material keshi: bir xil rangdagi devorlar bitta material bilan chiziladi. */
    _std(color, opts = {}) {
        const key = [color, ...Object.entries(opts).map(([k, v]) => `${k}:${v && v.uuid ? v.uuid : v}`)].join("|");
        if (!this._mc.has(key)) {
            const m = new this.THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0, ...opts });
            this._disposables.push(m);
            this._mc.set(key, m);
        }
        return this._mc.get(key);
    }

    _glass() {
        // Tunda oynalar ichkaridan iliq yorug' bilan yonadi.
        return this.night
            ? this._std(C.glass, { roughness: 0.2, metalness: 0.3, emissive: 0xffc878, emissiveIntensity: 0.55 })
            : this._std(C.glass, { roughness: 0.15, metalness: 0.4, emissive: 0x0b1a2a });
    }

    _mesh(geo, mat) {
        // Material keshdan bo'lsa ham qo'shiladi — tozalashda Set takrorni olib tashlaydi.
        this._disposables.push(geo, mat);
        return new this.THREE.Mesh(geo, mat);
    }

    // ------------------------------------------------------------------
    // Dunyo: yer, yo'llar, binolar, daraxtlar
    // ------------------------------------------------------------------
    _layout(nodes) {
        const scene = this.data;
        if (scene.mode === "chain") {
            // Server bergan sxema zich — binolar va yo'llar sig'ishi uchun kengaytiriladi.
            const k = 1.5;
            return nodes.map((n) => ({ x: (n.pos || [0, 0])[0] * k, z: (n.pos || [0, 0])[1] * k }));
        }
        // farm: guruhlar — qatorlar (z), guruh ichida — ustunlar (x).
        const groups = [];
        const byGroup = new Map();
        for (const n of nodes) {
            const g = n.group || "";
            if (!byGroup.has(g)) {
                byGroup.set(g, []);
                groups.push(g);
            }
            byGroup.get(g).push(n);
        }
        const perRow = 6;
        const dx = 4.0;
        const dz = 4.6;
        const out = new Map();
        let row = 0;
        this._groupRows = [];
        for (const g of groups) {
            const items = byGroup.get(g);
            const rows = Math.ceil(items.length / perRow);
            this._groupRows.push({ label: g, row, rows });
            items.forEach((n, i) => {
                const r = row + Math.floor(i / perRow);
                const c = i % perRow;
                const cols = Math.min(items.length - Math.floor(i / perRow) * perRow, perRow);
                out.set(n, { x: (c - (cols - 1) / 2) * dx, z: r * dz });
            });
            row += rows;
        }
        const totalRows = row;
        for (const p of out.values()) {
            p.z -= ((totalRows - 1) * dz) / 2;
        }
        this._rowDz = dz;
        this._totalRows = totalRows;
        return nodes.map((n) => out.get(n));
    }

    _buildWorld() {
        const THREE = this.THREE;
        const nodes = this.data.nodes || [];
        const positions = this._layout(nodes);
        const chain = this.data.mode === "chain";

        let minX = -5, maxX = 5, minZ = -4, maxZ = 4;
        for (const p of positions) {
            minX = Math.min(minX, p.x - 2.2);
            maxX = Math.max(maxX, p.x + 2.2);
            minZ = Math.min(minZ, p.z - 2.2);
            maxZ = Math.max(maxZ, p.z + 2.2);
        }
        const cx = (minX + maxX) / 2;
        const cz = (minZ + maxZ) / 2;
        const size = Math.max(maxX - minX, maxZ - minZ) + 4;
        this._rect = { minX, maxX, minZ, maxZ };
        this._avoid = []; // daraxt ekilmaydigan joylar: [x, z, radius]

        // Yer: katta o't maydoni — chetlari tumanga singib ketadi.
        const R = Math.max(140, size * 5);
        const grass = this._t("grass");
        grass.repeat.set(R / 3, R / 3);
        const ground = this._mesh(new THREE.CircleGeometry(R, 64), this._std(0xffffff, { map: grass, roughness: 1 }));
        ground.rotation.x = -Math.PI / 2;
        ground.position.set(cx, 0, cz);
        ground.receiveShadow = true;
        this.scene3.add(ground);

        // Korxona hududi uchun yengil qum-shag'al maydon.
        const yard = this._mesh(
            new THREE.PlaneGeometry(maxX - minX + 3, maxZ - minZ + 3),
            this._std(0xb9b48f, { roughness: 1, transparent: true, opacity: 0.35 })
        );
        yard.rotation.x = -Math.PI / 2;
        yard.position.set(cx, 0.005, cz);
        yard.receiveShadow = true;
        this.scene3.add(yard);

        // Binolar.
        const centers = new Map();
        nodes.forEach((node, index) => {
            const p = positions[index];
            const H = 0.35 + Math.max(0, Math.min(1, node.h ?? 0.5)) * 0.65;
            const built = this._shape(node.shape, H, node.status);
            const group = built.group;
            group.position.set(p.x, 0, p.z);
            group.traverse((o) => {
                if (o.isMesh) {
                    o.castShadow = true;
                    o.receiveShadow = true;
                }
            });
            this._sitePad(group, built, node.status);
            group.traverse((o) => {
                if (o.isMesh && !o.userData.noPick) {
                    o.userData.nodeIndex = index;
                    this._pickables.push(o);
                }
            });
            this.scene3.add(group);
            this._nodeGroups[index] = group;
            this._avoid.push([p.x, p.z, Math.hypot(built.pad[0], built.pad[1]) / 2 + 0.6]);
            centers.set(node.id, new THREE.Vector3(p.x, 0, p.z));
            // Ko'p bino bo'lsa yorliq faqat nom — qiymat sichqoncha olib borilganda chiqadi.
            const compact = !chain && nodes.length > 8;
            this._nodeLabels[index] = this._addLabel({ x: p.x, y: built.top + 0.55, z: p.z }, node.label, compact ? "" : node.display,
                node.status);
        });

        // Yo'llar: zanjirda — bo'g'inlar orasida, fermada — har qator oldida.
        const rnd = seeded(nodes.length * 31 + 7);
        if (chain) {
            for (const [a, b] of this.data.links || []) {
                const pa = centers.get(a);
                const pb = centers.get(b);
                if (!pa || !pb) {
                    continue;
                }
                const mid = pa.clone().add(pb).multiplyScalar(0.5);
                const dir = pb.clone().sub(pa);
                const perp = new THREE.Vector3(-dir.z, 0, dir.x).normalize();
                mid.addScaledVector(perp, dir.length() * 0.12 * (rnd() > 0.5 ? 1 : -1));
                const curve = new THREE.QuadraticBezierCurve3(pa, mid, pb);
                this._road(curve, 0.62);
                // Oqim — yo'l bo'ylab boradigan yuk mashinalari.
                for (let i = 0; i < 2; i++) {
                    this._addVehicle(curve, i / 2 + rnd() * 0.2, 0.9 + rnd() * 0.3, 0.3, true);
                }
            }
        } else if (this._groupRows) {
            for (const g of this._groupRows) {
                for (let r = 0; r < g.rows; r++) {
                    const z = (g.row + r) * this._rowDz - ((this._totalRows - 1) * this._rowDz) / 2 + 1.75;
                    const curve = new THREE.LineCurve3(
                        new THREE.Vector3(minX - 0.5, 0, z), new THREE.Vector3(maxX + 0.5, 0, z));
                    this._road(curve, 0.7);
                }
                if (g.label) {
                    const z0 = g.row * this._rowDz - ((this._totalRows - 1) * this._rowDz) / 2;
                    const z1 = z0 + (g.rows - 1) * this._rowDz;
                    this._addLabel({ x: minX - 0.8, y: 0.5, z: (z0 + z1) / 2 }, g.label, "", "group");
                }
            }
        }

        // Korxona yonidan o'tadigan katta yo'l — manzaraga jon kiritadi.
        const hz = maxZ + 3.2;
        const highway = new THREE.LineCurve3(new THREE.Vector3(cx - R * 0.7, 0, hz), new THREE.Vector3(cx + R * 0.7, 0, hz));
        this._road(highway, 1.1);
        const back = new THREE.LineCurve3(highway.v2, highway.v1);
        for (let i = 0; i < 4; i++) {
            this._addVehicle(i % 2 ? highway : back, rnd(), 2.2 + rnd() * 1.2, 0.42, false, 0.25);
        }

        this._trees(cx, cz, R, hz);
        this._farmland(cx, cz, hz);
        return { cx, cz, size };
    }

    /** Bino ostidagi beton maydon, holat hoshiyasi va mayoq. */
    _sitePad(group, built, status) {
        const THREE = this.THREE;
        const [w, d] = built.pad;
        const color = STATUS[status] || STATUS.neutral;
        if (built.concrete !== false) {
            const conc = this._t("concrete");
            const pad = this._mesh(new THREE.BoxGeometry(w, 0.06, d), this._std(0xffffff, { map: conc }));
            pad.position.y = 0.03;
            pad.receiveShadow = true;
            group.add(pad);
        }
        // Hoshiya: to'rt tomonda ingichka rangli chiziq.
        const edge = this._std(color, { emissive: color, emissiveIntensity: 0.25, roughness: 0.6 });
        const t = 0.07;
        for (const [ew, ed, ex, ez] of [
            [w + t, t, 0, d / 2], [w + t, t, 0, -d / 2], [t, d + t, w / 2, 0], [t, d + t, -w / 2, 0],
        ]) {
            const m = this._mesh(new THREE.BoxGeometry(ew, 0.075, ed), edge);
            m.position.set(ex, 0.035, ez);
            group.add(m);
        }
        // Mayoq: burchakdagi ustun va yonib turgan chiroq.
        const pole = this._mesh(new THREE.CylinderGeometry(0.025, 0.03, 0.7, 8), this._std(C.trim, { metalness: 0.6, roughness: 0.4 }));
        pole.position.set(w / 2 - 0.12, 0.35, d / 2 - 0.12);
        group.add(pole);
        const lampMat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 1.4, roughness: 0.3 });
        const lamp = this._mesh(new THREE.SphereGeometry(0.075, 16, 12), lampMat);
        lamp.position.set(w / 2 - 0.12, 0.74, d / 2 - 0.12);
        group.add(lamp);
        if (status === "bad") {
            this._beacons.push(lampMat);
            const ringMat = new THREE.MeshBasicMaterial({
                color, transparent: true, opacity: 0.6, side: THREE.DoubleSide, depthWrite: false,
            });
            const ring = this._mesh(new THREE.RingGeometry(0.92, 1.0, 64), ringMat);
            ring.rotation.x = -Math.PI / 2;
            ring.position.y = 0.09;
            ring.userData.noPick = true;
            ring.userData.base = Math.max(w, d) * 0.55;
            group.add(ring);
            this._pulses.push(ring);
        }
    }

    /** Yassi lenta ko'rinishidagi asfalt yo'l (egri chiziq bo'ylab). */
    _road(curve, width) {
        const THREE = this.THREE;
        const steps = Math.max(2, Math.round(curve.getLength() * 3));
        const pos = [];
        const uv = [];
        const idx = [];
        let dist = 0;
        let prev = null;
        for (let i = 0; i <= steps; i++) {
            const p = curve.getPoint(i / steps);
            const tg = curve.getTangent(i / steps);
            const nx = -tg.z;
            const nz = tg.x;
            if (prev) {
                dist += p.distanceTo(prev);
            }
            prev = p;
            pos.push(p.x + nx * width / 2, 0.02, p.z + nz * width / 2, p.x - nx * width / 2, 0.02, p.z - nz * width / 2);
            uv.push(0, dist / 1.4, 1, dist / 1.4);
            if (i < steps) {
                const a = i * 2;
                idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
            }
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
        geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
        geo.setIndex(idx);
        geo.computeVertexNormals();
        const mat = this._std(C.asphalt, {
            map: this._t("road"), roughness: 0.95, side: THREE.DoubleSide,
            polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
        });
        const road = this._mesh(geo, mat);
        road.receiveShadow = true;
        this.scene3.add(road);
        for (let i = 0; i <= 8; i++) {
            const p = curve.getPoint(i / 8);
            this._avoid.push([p.x, p.z, width / 2 + 0.5]);
        }
    }

    /** `speed` — birlik/soniya; egri chiziq uzunligiga bo'linib, t qadamiga aylanadi. */
    _addVehicle(curve, t, speed, scale, fade, lane = 0.15) {
        const colors = [0xe3572f, 0x2f6fe3, 0xf2b134, 0x3a9d5d, 0xf8fafc];
        const v = this._truckModel(colors[this._vehicles.length % colors.length]);
        v.scale.setScalar(scale);
        v.traverse((o) => {
            if (o.isMesh) {
                o.castShadow = true;
            }
        });
        this.scene3.add(v);
        this._vehicles.push({ curve, obj: v, t, speed: speed / Math.max(0.5, curve.getLength()), fade, lane, scale });
    }

    /** Atrofga daraxtlar — instanced, yuzlab daraxt bitta chizish chaqiruvida. */
    _trees(cx, cz, R, hz) {
        const THREE = this.THREE;
        const rnd = seeded(4242);
        const { minX, maxX, minZ, maxZ } = this._rect;
        const spots = [];
        const free = (x, z) => {
            if (x > minX - 0.8 && x < maxX + 0.8 && z > minZ - 0.8 && z < maxZ + 0.8) {
                // Hudud ichida faqat bo'sh joylarga.
                for (const [ax, az, ar] of this._avoid) {
                    if (Math.hypot(x - ax, z - az) < ar) {
                        return false;
                    }
                }
                return rnd() < 0.35;
            }
            if (Math.abs(z - hz) < 1.3) {
                return false;
            }
            for (const [ax, az, ar] of this._avoid) {
                if (Math.hypot(x - ax, z - az) < ar) {
                    return false;
                }
            }
            return true;
        };
        // Kichik sahnada daraxt kam — bino o'rmon ichida qolib ketmasin.
        const band = Math.max(4, Math.min(9, (maxX - minX) * 0.3));
        const want = Math.min(230, Math.round((maxX - minX + band * 2) * (maxZ - minZ + band * 2) * 0.12));
        let tries = 0;
        while (spots.length < want && tries < 4000) {
            tries++;
            const x = minX - band + rnd() * (maxX - minX + band * 2);
            const z = minZ - band + rnd() * (maxZ - minZ + band * 2);
            if (free(x, z)) {
                spots.push([x, z, 0.7 + rnd() * 0.7, rnd()]);
            }
        }
        // Yo'l bo'ylab terak qatori.
        for (let x = minX - 6; x < maxX + 6; x += 1.6) {
            spots.push([x, hz - 1.0, 1.1 + rnd() * 0.3, 0.95]);
        }

        const dummy = new THREE.Object3D();
        const leafy = spots.filter((s) => s[3] < 0.62);
        const conifer = spots.filter((s) => s[3] >= 0.62);
        const trunkGeo = new THREE.CylinderGeometry(0.05, 0.08, 0.5, 6);
        trunkGeo.translate(0, 0.25, 0);
        const trunks = new THREE.InstancedMesh(trunkGeo, this._std(0x6b4a2f), spots.length);
        const crownGeo = new THREE.IcosahedronGeometry(0.42, 1);
        crownGeo.translate(0, 0.78, 0);
        const crowns = new THREE.InstancedMesh(crownGeo, this._std(0xffffff, { flatShading: true }), leafy.length);
        const coneGeo = new THREE.ConeGeometry(0.34, 1.15, 7);
        coneGeo.translate(0, 1.0, 0);
        const cones = new THREE.InstancedMesh(coneGeo, this._std(0xffffff, { flatShading: true }), conifer.length);
        this._disposables.push(trunkGeo, crownGeo, coneGeo);
        const col = new THREE.Color();
        const greens = [0x4f7f36, 0x5c8f3d, 0x3f6e2f, 0x6a9a44, 0x7a9c3c];
        spots.forEach(([x, z, s], i) => {
            dummy.position.set(x, 0, z);
            dummy.rotation.set(0, i * 1.7, 0);
            dummy.scale.set(s, s * (0.9 + (i % 5) * 0.06), s);
            dummy.updateMatrix();
            trunks.setMatrixAt(i, dummy.matrix);
        });
        leafy.forEach(([x, z, s], i) => {
            dummy.position.set(x, 0, z);
            dummy.rotation.set(0, i, 0);
            dummy.scale.set(s, s * (0.85 + (i % 4) * 0.1), s);
            dummy.updateMatrix();
            crowns.setMatrixAt(i, dummy.matrix);
            crowns.setColorAt(i, col.setHex(greens[i % greens.length]));
        });
        conifer.forEach(([x, z, s], i) => {
            dummy.position.set(x, 0, z);
            dummy.rotation.set(0, i, 0);
            dummy.scale.set(s * 0.8, s * 1.15, s * 0.8);
            dummy.updateMatrix();
            cones.setMatrixAt(i, dummy.matrix);
            cones.setColorAt(i, col.setHex(i % 3 ? 0x2f5b33 : 0x3d6b3a));
        });
        for (const m of [trunks, crowns, cones]) {
            m.castShadow = true;
            m.receiveShadow = true;
            m.instanceMatrix.needsUpdate = true;
            if (m.instanceColor) {
                m.instanceColor.needsUpdate = true;
            }
            this.scene3.add(m);
        }
    }

    /** Uzoqdagi ekin dalalari — chorsi-chorsi yamoqlar. */
    _farmland(cx, cz, hz) {
        const THREE = this.THREE;
        const rnd = seeded(99);
        const { minX, maxX, minZ, maxZ } = this._rect;
        const tints = [0x6f9a3c, 0xc9a94a, 0x5d8c34, 0xb08d45, 0x7aa443, 0xd6bf63];
        const tex = this._t("crops");
        for (let i = 0; i < 16; i++) {
            const ang = (i / 16) * Math.PI * 2 + rnd() * 0.3;
            const dist = 0.5 * Math.max(maxX - minX, maxZ - minZ) + 14 + rnd() * 14;
            const x = cx + Math.cos(ang) * dist;
            const z = cz + Math.sin(ang) * dist * 0.8;
            if (Math.abs(z - hz) < 5) {
                continue;
            }
            const w = 6 + rnd() * 7;
            const d = 5 + rnd() * 6;
            const patch = this._mesh(new THREE.PlaneGeometry(w, d), this._std(tints[i % tints.length], { map: tex, roughness: 1 }));
            patch.rotation.x = -Math.PI / 2;
            patch.rotation.z = rnd() * 0.6 - 0.3;
            patch.position.set(x, 0.01, z);
            patch.receiveShadow = true;
            this.scene3.add(patch);
        }
    }

    // ------------------------------------------------------------------
    // Binolar — har bo'limning tanish ko'rinishi.
    // Har biri { group, pad: [eni, bo'yi], top: balandlik } qaytaradi.
    // ------------------------------------------------------------------
    _shape(shape, H, status) {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const add = (geo, mat, x = 0, y = 0, z = 0, parent = g) => {
            const m = this._mesh(geo, mat);
            m.position.set(x, y, z);
            parent.add(m);
            return m;
        };
        const box = (w, h, d, mat, x, y, z, parent) => add(new THREE.BoxGeometry(w, h, d), mat, x, y, z, parent);
        const builders = {
            barn: () => this._barn(g, box, add, H),
            silo: () => this._mill(g, box, add, H),
            dome: () => this._hatchery(g, box, add, H),
            factory: () => this._plant(g, box, add, H),
            shop: () => this._shop(g, box, add, H),
            bank: () => this._office(g, box, add, H),
            crates: () => this._warehouse(g, box, add, H),
            field: () => this._field(g, box, add, H, status),
            truck: () => this._depot(g, box, add, H),
        };
        const info = (builders[shape] || builders.barn)();
        return { group: g, ...info };
    }

    /** Ikki qiyalik tom: devor uchburchagi + ikki tom tunukasi. Tizma X o'qi bo'ylab. */
    _gable(g, len, span, wallH, rise, roofMat, wallMat, x = 0, z = 0) {
        const THREE = this.THREE;
        const tri = new THREE.Shape();
        tri.moveTo(-span / 2, 0);
        tri.lineTo(span / 2, 0);
        tri.lineTo(0, rise);
        tri.lineTo(-span / 2, 0);
        const geo = new THREE.ExtrudeGeometry(tri, { depth: len, bevelEnabled: false });
        geo.translate(0, 0, -len / 2);
        const gable = this._mesh(geo, wallMat);
        gable.rotation.y = Math.PI / 2;
        gable.position.set(x, wallH, z);
        g.add(gable);
        const half = span / 2 + 0.08;
        const slope = Math.hypot(half, rise);
        const ang = Math.atan2(rise, span / 2);
        for (const side of [1, -1]) {
            const slab = this._mesh(new THREE.BoxGeometry(len + 0.16, 0.035, slope), roofMat);
            slab.rotation.x = side * ang;
            slab.position.set(x, wallH + rise / 2 + 0.02 - 0.04, z + (side * span) / 4 + side * 0.02);
            g.add(slab);
        }
    }

    _barn(g, box, add, H) {
        const THREE = this.THREE;
        const L = 2.8;
        const S = 1.2;
        const wallH = 0.42 + H * 0.3;
        const rise = 0.34;
        const wall = this._std(0xffffff, { map: this._t("siding") });
        const roof = this._std(C.roofRed, { map: this._t("corrugated"), roughness: 0.55, metalness: 0.3 });
        box(L, wallH, S, wall, 0, wallH / 2, 0);
        this._gable(g, L, S, wallH, rise, roof, this._std(C.wall));
        // Shamollatish tirqishlari va tizma ventilyatsiyasi.
        const dark = this._std(0x3b4148, { roughness: 0.5 });
        for (const z of [S / 2 + 0.005, -S / 2 - 0.005]) {
            for (let i = 0; i < 7; i++) {
                box(0.24, 0.09, 0.012, dark, -L / 2 + 0.3 + i * 0.37, wallH * 0.66, z);
            }
        }
        box(L * 0.85, 0.07, 0.14, this._std(C.metal, { metalness: 0.5, roughness: 0.4 }), 0, wallH + rise + 0.02, 0);
        // Torets: aylanib turgan ventilyatorlar.
        for (const z of [-0.28, 0.28]) {
            box(0.03, 0.34, 0.34, this._std(0x6b7480), -L / 2 - 0.015, wallH * 0.48, z);
            const fan = new THREE.Group();
            fan.position.set(-L / 2 - 0.04, wallH * 0.48, z);
            for (const r of [0, Math.PI / 2]) {
                const b = box(0.012, 0.28, 0.05, this._std(0x2a2f35), 0, 0, 0, fan);
                b.rotation.x = r;
            }
            g.add(fan);
            this._spinners.push({ obj: fan, axis: "x", speed: 9 });
        }
        box(0.012, 0.38, 0.36, this._std(C.trim), L / 2 + 0.006, 0.19, 0);
        // Yem bunkeri.
        const metal = this._std(0xffffff, { map: this._t("ribs"), metalness: 0.55, roughness: 0.35 });
        const fx = L / 2 - 0.35;
        const fz = S / 2 + 0.33;
        for (const [lx, lz] of [[-0.12, -0.12], [0.12, -0.12], [-0.12, 0.12], [0.12, 0.12]]) {
            add(new THREE.CylinderGeometry(0.012, 0.012, 0.32, 5), this._std(C.trim), fx + lx, 0.16, fz + lz);
        }
        add(new THREE.ConeGeometry(0.18, 0.14, 16), metal, fx, 0.3, fz).rotation.x = Math.PI;
        add(new THREE.CylinderGeometry(0.18, 0.18, 0.5, 16), metal, fx, 0.62, fz);
        add(new THREE.ConeGeometry(0.19, 0.14, 16), metal, fx, 0.94, fz);
        return { pad: [3.3, 2.3], top: Math.max(wallH + rise, 1.0) };
    }

    _mill(g, box, add, H) {
        const THREE = this.THREE;
        const metal = this._std(0xffffff, { map: this._t("ribs"), metalness: 0.6, roughness: 0.35 });
        const band = this._std(0x8c959e, { metalness: 0.6, roughness: 0.4 });
        const hs = 1.0 + H * 1.5;
        const sx = [-0.95, -0.15, 0.65];
        for (const x of sx) {
            add(new THREE.CylinderGeometry(0.38, 0.38, hs, 28), metal, x, hs / 2, -0.4);
            for (const y of [0.25, hs * 0.5, hs - 0.1]) {
                add(new THREE.CylinderGeometry(0.392, 0.392, 0.04, 28), band, x, y, -0.4);
            }
            add(new THREE.ConeGeometry(0.41, 0.3, 28), this._std(0xdfe4e8, { metalness: 0.6, roughness: 0.3 }), x, hs + 0.15, -0.4);
        }
        // Ko'tarma minora va konveyer.
        const yellow = this._std(C.yellow, { roughness: 0.6 });
        box(0.26, hs + 0.75, 0.26, yellow, 1.3, (hs + 0.75) / 2, -0.4);
        box(2.5, 0.06, 0.14, this._std(C.trim, { metalness: 0.5 }), 0.2, hs + 0.35, -0.4);
        // Tegirmon binosi.
        const wallH = 0.62;
        box(2.6, wallH, 0.8, this._std(C.wallWarm), 0, wallH / 2, 0.62);
        this._gable(g, 2.6, 0.8, wallH, 0.24, this._std(C.roofGrey, { map: this._t("corrugated"), metalness: 0.4, roughness: 0.5 }),
            this._std(C.wallWarm), 0, 0.62);
        for (let i = 0; i < 4; i++) {
            box(0.26, 0.18, 0.01, this._glass(), -0.9 + i * 0.6, wallH * 0.62, 1.025);
        }
        box(0.44, 0.42, 0.01, this._std(0xffffff, { map: this._t("shutter") }), 0.95, 0.21, 1.026);
        return { pad: [3.4, 2.4], top: hs + 0.75 };
    }

    _hatchery(g, box, add, H) {
        const THREE = this.THREE;
        const h = 0.6 + H * 0.4;
        box(2.4, h, 1.6, this._std(0xf7f7f4, { roughness: 0.7 }), 0, h / 2, 0);
        box(2.46, 0.07, 1.66, this._std(0x9aa3ab), 0, h + 0.035, 0);
        box(2.42, 0.17, 1.62, this._glass(), 0, h * 0.64, 0);
        // Kirish soyaboni va eshik.
        box(0.8, 0.04, 0.42, this._std(C.trim), 0.5, 0.44, 1.0);
        for (const x of [0.16, 0.84]) {
            add(new THREE.CylinderGeometry(0.02, 0.02, 0.42, 6), this._std(C.trim), x, 0.21, 1.17);
        }
        box(0.42, 0.36, 0.01, this._glass(), 0.5, 0.18, 0.806);
        // Brend yozuvi tushadigan panel.
        box(0.9, 0.14, 0.02, this._std(C.brand, { emissive: C.brand, emissiveIntensity: 0.45 }), -0.55, h * 0.88, 0.81);
        // Tomdagi konditsionerlar — parvona aylanadi.
        for (const [x, z] of [[-0.7, -0.35], [0, -0.35], [0.7, -0.35]]) {
            box(0.36, 0.16, 0.36, this._std(0xb7bec5, { metalness: 0.3, roughness: 0.5 }), x, h + 0.15, z);
            const fan = new THREE.Group();
            fan.position.set(x, h + 0.235, z);
            for (const r of [0, Math.PI / 2]) {
                box(0.26, 0.01, 0.04, this._std(0x2a2f35), 0, 0, 0, fan).rotation.y = r;
            }
            g.add(fan);
            this._spinners.push({ obj: fan, axis: "y", speed: 7 });
        }
        return { pad: [3.0, 2.6], top: h + 0.3 };
    }

    _plant(g, box, add, H) {
        const THREE = this.THREE;
        const h = 0.62 + H * 0.35;
        const wall = this._std(C.wallWarm);
        box(2.4, h, 1.5, wall, 0, h / 2, -0.1);
        // Arra tishli tom: tik tomoni oynali.
        const roof = this._std(C.roofGrey, { map: this._t("corrugated"), metalness: 0.4, roughness: 0.5 });
        const tri = new THREE.Shape();
        tri.moveTo(0, 0);
        tri.lineTo(0.6, 0);
        tri.lineTo(0, 0.3);
        tri.lineTo(0, 0);
        for (let i = 0; i < 4; i++) {
            const geo = new THREE.ExtrudeGeometry(tri, { depth: 1.5, bevelEnabled: false });
            geo.translate(0, 0, -0.75);
            const tooth = this._mesh(geo, roof);
            tooth.position.set(-1.2 + i * 0.6, h, -0.1);
            g.add(tooth);
            box(0.012, 0.24, 1.4, this._glass(), -1.2 + i * 0.6 - 0.008, h + 0.13, -0.1);
        }
        // Yuklash rampasi va darvozalar.
        box(2.0, 0.14, 0.32, this._std(C.concrete), 0, 0.07, 0.81);
        for (let i = 0; i < 3; i++) {
            box(0.42, 0.42, 0.012, this._std(0xffffff, { map: this._t("shutter") }), -0.6 + i * 0.6, 0.35, 0.656);
        }
        box(2.42, 0.08, 0.06, this._std(0x2f7fd1), 0, h - 0.12, 0.66);
        // Qizil-oq mo'ri va tutun.
        const ch = 1.5 + H * 0.6;
        const cx = 0.95;
        const cz = -0.6;
        add(new THREE.CylinderGeometry(0.09, 0.13, ch, 14), this._std(0xf1f1ee), cx, ch / 2, cz);
        for (const y of [ch - 0.12, ch - 0.42]) {
            add(new THREE.CylinderGeometry(0.095, 0.1, 0.14, 14), this._std(0xc8372d), cx, y, cz);
        }
        const smokeGeo = new THREE.IcosahedronGeometry(0.16, 1);
        this._disposables.push(smokeGeo);
        for (let i = 0; i < 7; i++) {
            const mat = new THREE.MeshStandardMaterial({ color: 0xe8eaec, transparent: true, opacity: 0.5, depthWrite: false, roughness: 1 });
            this._disposables.push(mat);
            const puff = new THREE.Mesh(smokeGeo, mat);
            puff.userData.noPick = true;
            g.add(puff);
            this._smoke.push({ puff, origin: [cx, ch, cz], t: i / 7 });
        }
        return { pad: [3.0, 2.4], top: ch + 0.1 };
    }

    _shop(g, box, add, H) {
        const THREE = this.THREE;
        const h = 0.72 + H * 0.25;
        box(2.2, h, 1.3, this._std(C.wallWarm), 0, h / 2, -0.25);
        box(2.26, 0.1, 1.36, this._std(0x7a838c), 0, h + 0.05, -0.25);
        box(1.9, 0.46, 0.015, this._std(0x8fc3e8, { roughness: 0.1, metalness: 0.3, emissive: 0x3b6f94, emissiveIntensity: 0.6 }), 0, 0.3, 0.41);
        for (const x of [-0.95, -0.32, 0.32, 0.95]) {
            box(0.04, 0.48, 0.03, this._std(C.trim), x, 0.3, 0.42);
        }
        const awning = box(2.1, 0.03, 0.42, this._std(0xffffff, { map: this._t("awning") }), 0, 0.64, 0.6);
        awning.rotation.x = 0.32;
        // Tomdagi yorug' peshlavha.
        for (const x of [-0.5, 0.5]) {
            box(0.04, 0.2, 0.04, this._std(C.trim), x, h + 0.2, 0.25);
        }
        box(1.5, 0.3, 0.06, this._std(C.brand, { emissive: C.brand, emissiveIntensity: 0.7, roughness: 0.4 }), 0, h + 0.42, 0.25);
        // Avtoturargoh: chiziqlar va mashinalar.
        const line = this._std(0xf3f4f6);
        for (const x of [-1.1, -0.38, 0.38, 1.1]) {
            box(0.03, 0.005, 0.55, line, x, 0.065, 1.05);
        }
        const car1 = this._car(0xd94b3d);
        car1.position.set(-0.74, 0.06, 1.05);
        g.add(car1);
        const car2 = this._car(0x34495e);
        car2.position.set(0.74, 0.06, 1.05);
        car2.rotation.y = Math.PI;
        g.add(car2);
        return { pad: [3.0, 2.9], top: h + 0.6 };
    }

    _office(g, box, add, H) {
        const THREE = this.THREE;
        const floors = 2 + Math.round(H * 5);
        const fh = 0.3;
        const th = floors * fh;
        const tex = this._t("windows").clone();
        tex.needsUpdate = true;
        tex.repeat.set(2, floors / 2);
        this._disposables.push(tex);
        const facade = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45, metalness: 0.2 });
        if (this.night) {
            const lit = this._t("windowsLit").clone();
            lit.needsUpdate = true;
            lit.repeat.copy(tex.repeat);
            this._disposables.push(lit);
            facade.emissive.setHex(0xffd9a0);
            facade.emissiveMap = lit;
            facade.emissiveIntensity = 1.1;
        }
        const roofM = this._std(0x8c949b);
        const tower = this._mesh(new THREE.BoxGeometry(1.3, th, 1.0), facade);
        tower.material = [facade, facade, roofM, roofM, facade, facade];
        tower.position.set(0, 0.35 + th / 2, -0.35);
        g.add(tower);
        box(1.38, 0.08, 1.08, this._std(0x5f6870), 0, 0.35 + th + 0.04, -0.35);
        box(0.4, 0.18, 0.3, this._std(0xaab2b9), 0.3, 0.35 + th + 0.17, -0.5);
        // Pastki qavat — kolonnali kirish.
        box(2.1, 0.35, 1.7, this._std(0xeeeae0), 0, 0.175, 0);
        box(2.18, 0.05, 1.78, this._std(0xd6cfbf), 0, 0.375, 0);
        box(1.4, 0.26, 0.012, this._glass(), 0, 0.15, 0.856);
        for (const x of [-0.6, -0.2, 0.2, 0.6]) {
            add(new THREE.CylinderGeometry(0.04, 0.04, 0.34, 10), this._std(0xf7f4ec), x, 0.17, 0.93);
        }
        box(1.5, 0.04, 0.24, this._std(0xf7f4ec), 0, 0.36, 0.95);
        // Oltin tanga — moliya belgisi.
        const coin = add(new THREE.CylinderGeometry(0.2, 0.2, 0.05, 32),
            this._std(0xf2c14e, { metalness: 0.9, roughness: 0.25, emissive: 0x3a2a00 }), -0.75, 0.62, 0.55);
        coin.rotation.order = "YXZ";
        coin.rotation.x = Math.PI / 2;
        this._spinners.push({ obj: coin, axis: "y", speed: 1.4 });
        return { pad: [2.8, 2.4], top: 0.35 + th + 0.3 };
    }

    _warehouse(g, box, add, H) {
        const THREE = this.THREE;
        const wall = this._std(0xffffff, { map: this._t("siding") });
        box(2.0, 0.55, 1.35, wall, -0.35, 0.275, -0.1);
        const arch = add(new THREE.CylinderGeometry(0.7, 0.7, 2.06, 28, 1, false, 0, Math.PI),
            this._std(C.roofGreen, { map: this._t("ribs"), metalness: 0.35, roughness: 0.5 }), -0.35, 0.55, -0.1);
        arch.rotation.z = Math.PI / 2;
        arch.scale.set(1, 0.5, 0.98);
        const shutter = this._std(0xffffff, { map: this._t("shutter") });
        for (const x of [-0.85, 0.15]) {
            box(0.5, 0.42, 0.012, shutter, x, 0.23, 0.58);
        }
        // Paletlarda yashiklar — hajm bilan ko'payadi.
        const stacks = 1 + Math.round(H * 5);
        const pallet = this._std(C.wood);
        const crateA = this._std(C.woodLight, { roughness: 0.9 });
        const crateB = this._std(0xb5824a, { roughness: 0.9 });
        for (let i = 0; i < stacks; i++) {
            const x = 0.95 + (i % 2) * 0.42;
            const z = -0.55 + Math.floor(i / 2) * 0.42;
            box(0.36, 0.05, 0.36, pallet, x, 0.09, z);
            const layers = i < stacks - 1 ? 2 : 1;
            for (let l = 0; l < layers; l++) {
                box(0.32, 0.26, 0.32, (i + l) % 2 ? crateA : crateB, x, 0.25 + l * 0.27, z);
            }
        }
        return { pad: [3.3, 2.2], top: 1.05 };
    }

    _field(g, box, add, H, status) {
        const THREE = this.THREE;
        box(2.8, 0.05, 2.3, this._std(0xffffff, { map: this._t("soil"), roughness: 1 }), 0, 0.025, 0);
        // O'simliklar — bitta instanced mesh; balandligi hosilga qarab.
        const rows = 9;
        const per = 13;
        const plantGeo = new THREE.ConeGeometry(0.07, 1, 5);
        plantGeo.translate(0, 0.5, 0);
        this._disposables.push(plantGeo);
        const plants = new THREE.InstancedMesh(plantGeo, this._std(0xffffff, { flatShading: true, roughness: 0.9 }), rows * per);
        this._disposables.push(plants);
        const dummy = new THREE.Object3D();
        const col = new THREE.Color();
        const tone = status === "bad" ? [0xb4a64a, 0xc9b257, 0x9c9a45] : [0x4f9a3a, 0x5aa843, 0x468c33];
        const ph = 0.12 + H * 0.4;
        let k = 0;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < per; c++) {
                dummy.position.set(-1.2 + c * 0.2, 0.05, -1.0 + r * 0.25);
                const s = 0.85 + ((r * 7 + c * 3) % 5) * 0.06;
                dummy.scale.set(s, ph * s, s);
                dummy.rotation.set(0, (r + c) * 0.7, 0);
                dummy.updateMatrix();
                plants.setMatrixAt(k, dummy.matrix);
                plants.setColorAt(k, col.setHex(tone[(r + c) % 3]));
                k++;
            }
        }
        plants.instanceMatrix.needsUpdate = true;
        if (plants.instanceColor) {
            plants.instanceColor.needsUpdate = true;
        }
        g.add(plants);
        // Traktor va pichan o'ramlari.
        const tractor = this._tractor();
        tractor.position.set(1.15, 0.05, 1.3);
        tractor.rotation.y = -Math.PI / 2;
        g.add(tractor);
        const hay = this._std(0xd9b866, { roughness: 1 });
        for (const z of [-1.0, -0.62]) {
            add(new THREE.CylinderGeometry(0.15, 0.15, 0.2, 16), hay, -1.65, 0.15, z).rotation.z = Math.PI / 2;
        }
        return { pad: [3.0, 2.6], top: 0.35 + ph, concrete: false };
    }

    _depot(g, box, add, H) {
        const lot = box(2.9, 0.03, 2.3, this._std(0x5a5f66, { roughness: 0.95 }), 0, 0.075, 0);
        lot.receiveShadow = true;
        const line = this._std(0xf3f4f6);
        for (let i = 0; i < 5; i++) {
            box(0.03, 0.005, 1.0, line, -0.15 + i * 0.42, 0.093, 0.35);
        }
        // Garaj.
        const wallH = 0.6;
        box(1.0, wallH, 0.95, this._std(C.wallWarm), -0.85, wallH / 2, -0.55);
        this._gable(g, 1.0, 0.95, wallH, 0.22,
            this._std(C.roofGrey, { map: this._t("corrugated"), metalness: 0.4, roughness: 0.5 }), this._std(C.wallWarm), -0.85, -0.55);
        box(0.012, 0.44, 0.6, this._std(0xffffff, { map: this._t("shutter") }), -0.344, 0.22, -0.55);
        // Turgan yuk mashinalari — soni hajmga qarab.
        const n = 1 + Math.round(H * 3);
        const colors = [0xe3572f, 0x2f6fe3, 0x3a9d5d, 0xf2b134];
        for (let i = 0; i < n; i++) {
            const t = this._truckModel(colors[i % colors.length]);
            t.scale.setScalar(0.62);
            t.position.set(0.06 + i * 0.42, 0.09, 0.35);
            g.add(t);
        }
        return { pad: [3.1, 2.5], top: 1.0 };
    }

    // --- transport vositalari (old tomoni +Z) ---
    _truckModel(color) {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const b = (w, h, d, mat, x, y, z) => {
            const m = this._mesh(new THREE.BoxGeometry(w, h, d), mat);
            m.position.set(x, y, z);
            g.add(m);
            return m;
        };
        b(0.3, 0.06, 1.4, this._std(0x2b2f34), 0, 0.15, 0);
        b(0.44, 0.48, 1.0, this._std(0xf4f5f2, { roughness: 0.6 }), 0, 0.42, -0.18);
        b(0.44, 0.38, 0.34, this._std(color, { roughness: 0.45, metalness: 0.2 }), 0, 0.34, 0.52);
        b(0.38, 0.15, 0.012, this._glass(), 0, 0.42, 0.692);
        // Faralar — tunda yorqin yonadi.
        const lamp = this._std(0xfff4d6, { emissive: 0xfff1c4, emissiveIntensity: this.night ? 2.2 : 0.3 });
        for (const x of [-0.15, 0.15]) {
            b(0.08, 0.05, 0.012, lamp, x, 0.24, 0.692);
        }
        const wheel = this._std(C.tire, { roughness: 0.9 });
        for (const z of [0.5, -0.3, -0.5]) {
            for (const x of [-0.2, 0.2]) {
                const w = this._mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.08, 12), wheel);
                w.rotation.z = Math.PI / 2;
                w.position.set(x, 0.1, z);
                g.add(w);
            }
        }
        return g;
    }

    _car(color) {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const body = this._mesh(new THREE.BoxGeometry(0.3, 0.11, 0.56), this._std(color, { roughness: 0.35, metalness: 0.4 }));
        body.position.y = 0.11;
        const cab = this._mesh(new THREE.BoxGeometry(0.26, 0.1, 0.3), this._glass());
        cab.position.set(0, 0.215, -0.03);
        g.add(body, cab);
        const wheel = this._std(C.tire);
        for (const [x, z] of [[-0.15, 0.17], [0.15, 0.17], [-0.15, -0.17], [0.15, -0.17]]) {
            const w = this._mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.04, 10), wheel);
            w.rotation.z = Math.PI / 2;
            w.position.set(x, 0.055, z);
            g.add(w);
        }
        return g;
    }

    _tractor() {
        const THREE = this.THREE;
        const g = new THREE.Group();
        const green = this._std(0x2f8a3e, { roughness: 0.5, metalness: 0.2 });
        const add = (geo, mat, x, y, z) => {
            const m = this._mesh(geo, mat);
            m.position.set(x, y, z);
            g.add(m);
            return m;
        };
        add(new THREE.BoxGeometry(0.2, 0.14, 0.42), green, 0, 0.18, 0.05);
        add(new THREE.BoxGeometry(0.22, 0.2, 0.2), this._glass(), 0, 0.34, -0.06);
        add(new THREE.BoxGeometry(0.25, 0.02, 0.24), green, 0, 0.45, -0.06);
        add(new THREE.CylinderGeometry(0.015, 0.015, 0.14, 6), this._std(0x333333), 0.05, 0.31, 0.2);
        const tire = this._std(C.tire);
        for (const x of [-0.14, 0.14]) {
            add(new THREE.CylinderGeometry(0.14, 0.14, 0.08, 14), tire, x, 0.14, -0.08).rotation.z = Math.PI / 2;
            add(new THREE.CylinderGeometry(0.08, 0.08, 0.06, 12), tire, x, 0.08, 0.2).rotation.z = Math.PI / 2;
        }
        return g;
    }

    _addLabel(pos, title, value, status) {
        const layer = this.labelsRef.el;
        if (!layer) {
            return;
        }
        const el = document.createElement("div");
        el.className = `o_s3d_label o_s3d_${status || "neutral"}`;
        const t = document.createElement("div");
        t.className = "o_s3d_label_title";
        t.textContent = title || "";
        el.appendChild(t);
        if (value) {
            const v = document.createElement("div");
            v.className = "o_s3d_label_value";
            v.textContent = value;
            el.appendChild(v);
        }
        layer.appendChild(el);
        this._labels.push({ el, pos: new this.THREE.Vector3(pos.x, pos.y, pos.z) });
        return el;
    }

    // ------------------------------------------------------------------
    // Kamera boshqaruvi (aylantirish, yaqinlashtirish)
    // ------------------------------------------------------------------
    _setupOrbit(bounds) {
        this.target = new this.THREE.Vector3(bounds.cx, 0.6, bounds.cz);
        const chain = this.data.mode === "chain";
        this._home = {
            theta: chain ? -Math.PI / 7 : -Math.PI / 9,
            phi: chain ? 0.92 : 0.8,
            radius: Math.max(10, bounds.size * (chain ? 0.62 : 0.85)),
        };
        this.orbit = { ...this._home };
        this._minR = 5;
        this._maxR = Math.max(40, bounds.size * 2.2);
        this._applyCamera();
    }

    _applyCamera() {
        const { theta, phi, radius } = this.orbit;
        const t = this.target;
        this.camera.position.set(
            t.x + radius * Math.sin(phi) * Math.sin(theta),
            t.y + radius * Math.cos(phi),
            t.z + radius * Math.sin(phi) * Math.cos(theta)
        );
        this.camera.lookAt(t);
        // Tuman kamera masofasiga moslashadi: yaqin binolar tiniq, ufq xira.
        if (this.scene3?.fog) {
            this.scene3.fog.near = radius * 1.1;
            this.scene3.fog.far = radius * 3.4;
        }
    }

    resetView() {
        if (this.orbit) {
            Object.assign(this.orbit, this._home);
            this._applyCamera();
        }
    }

    toggleRotate() {
        this.state.autoRotate = !this.state.autoRotate;
    }

    zoom(factor) {
        if (!this.orbit) {
            return;
        }
        this.orbit.radius = Math.min(this._maxR, Math.max(this._minR, this.orbit.radius * factor));
        this._applyCamera();
    }

    _bindEvents() {
        const el = this.renderer.domElement;
        el.style.touchAction = "none";
        this._raycaster = new this.THREE.Raycaster();
        this._pointer = new this.THREE.Vector2();
        let drag = null;

        this._onDown = (ev) => {
            drag = { x: ev.clientX, y: ev.clientY, moved: 0, theta: this.orbit.theta, phi: this.orbit.phi };
            el.setPointerCapture(ev.pointerId);
            this._interacting = true;
        };
        this._onMove = (ev) => {
            if (drag) {
                const dx = ev.clientX - drag.x;
                const dy = ev.clientY - drag.y;
                drag.moved = Math.max(drag.moved, Math.abs(dx) + Math.abs(dy));
                this.orbit.theta = drag.theta - dx * 0.008;
                this.orbit.phi = Math.min(1.3, Math.max(0.25, drag.phi - dy * 0.006));
                this._applyCamera();
                return;
            }
            this._hoverAt(ev);
        };
        this._onUp = (ev) => {
            if (drag && drag.moved < 6) {
                const hit = this._hit(ev);
                if (hit !== null && this.props.onPick) {
                    this.props.onPick(this.data.nodes[hit]);
                }
            }
            drag = null;
            this._interacting = false;
        };
        this._onWheel = (ev) => {
            ev.preventDefault();
            this.zoom(ev.deltaY > 0 ? 1.1 : 0.9);
        };
        this._onLeave = () => {
            this._setHover(null);
        };
        el.addEventListener("pointerdown", this._onDown);
        el.addEventListener("pointermove", this._onMove);
        el.addEventListener("pointerup", this._onUp);
        el.addEventListener("pointerleave", this._onLeave);
        el.addEventListener("wheel", this._onWheel, { passive: false });
    }

    _hit(ev) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this._pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
        this._pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
        this._raycaster.setFromCamera(this._pointer, this.camera);
        const hits = this._raycaster.intersectObjects(this._pickables, false);
        return hits.length ? hits[0].object.userData.nodeIndex : null;
    }

    _hoverAt(ev) {
        const index = this._hit(ev);
        if (index === null) {
            this._setHover(null);
            return;
        }
        const rect = this.hostRef.el.getBoundingClientRect();
        const node = this.data.nodes[index];
        this._setHover(index, {
            label: node.label,
            display: node.display,
            metric: node.metric,
            status: node.status,
            x: ev.clientX - rect.left + 14,
            y: ev.clientY - rect.top + 14,
        });
    }

    _setHover(index, info = null) {
        if (this._hoverIndex !== index) {
            const groups = this._nodeGroups;
            if (this._hoverIndex != null && groups[this._hoverIndex]) {
                groups[this._hoverIndex].scale.setScalar(1);
                this._nodeLabels[this._hoverIndex]?.classList.remove("o_s3d_active");
            }
            if (index !== null && groups[index]) {
                groups[index].scale.setScalar(1.05);
                this._nodeLabels[index]?.classList.add("o_s3d_active");
            }
            this._hoverIndex = index;
            this.renderer.domElement.style.cursor = index !== null ? "pointer" : "grab";
        }
        this.state.hover = info;
    }

    // ------------------------------------------------------------------
    // Kadr sikli
    // ------------------------------------------------------------------
    _resize() {
        const host = this.hostRef.el;
        if (!host || !this.renderer) {
            return;
        }
        const w = host.clientWidth || 600;
        const h = host.clientHeight || 380;
        this.renderer.setSize(w, h);
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
    }

    _loop() {
        if (this._destroyed) {
            return;
        }
        this._raf = requestAnimationFrame(() => this._loop());
        if (!this._visible || document.hidden) {
            return;
        }
        const dt = Math.min(this.clock.getDelta(), 0.05);
        const t = this.clock.elapsedTime;
        if (this.state.autoRotate && !this._interacting && this._hoverIndex == null) {
            this.orbit.theta += dt * 0.08;
            this._applyCamera();
        }
        // Og'ish: yerda tarqaluvchi to'lqin va miltillovchi mayoq.
        const wave = (t % 1.8) / 1.8;
        for (const ring of this._pulses) {
            const s = ring.userData.base * (0.6 + wave * 1.1);
            ring.scale.set(s, s, s);
            ring.material.opacity = 0.75 * (1 - wave);
        }
        const blink = 0.5 + 0.5 * Math.sin(t * 6);
        for (const m of this._beacons) {
            m.emissiveIntensity = 0.4 + blink * 2.2;
        }
        for (const s of this._spinners) {
            s.obj.rotation[s.axis] += dt * s.speed;
        }
        for (const s of this._smoke) {
            s.t = (s.t + dt * 0.28) % 1;
            const k = s.t;
            s.puff.position.set(s.origin[0] + k * 0.5, s.origin[1] + 0.1 + k * 1.3, s.origin[2] - k * 0.2);
            s.puff.scale.setScalar(0.5 + k * 1.8);
            s.puff.material.opacity = 0.55 * (1 - k);
        }
        const tg = this._tmpT || (this._tmpT = new this.THREE.Vector3());
        for (const v of this._vehicles) {
            v.t = (v.t + dt * v.speed) % 1;
            const p = v.curve.getPoint(v.t);
            v.curve.getTangent(v.t, tg);
            v.obj.position.set(p.x - tg.z * v.lane, 0.02, p.z + tg.x * v.lane);
            v.obj.rotation.y = Math.atan2(tg.x, tg.z);
            if (v.fade) {
                // Bino ichidan chiqib, keyingisiga kirib ketgandek.
                const e = Math.min(1, Math.min(v.t, 1 - v.t) / 0.12);
                v.obj.scale.setScalar(v.scale * Math.max(0.001, e));
            }
        }
        this.renderer.render(this.scene3, this.camera);
        this._placeLabels();
    }

    _placeLabels() {
        const host = this.hostRef.el;
        if (!host) {
            return;
        }
        const w = host.clientWidth;
        const h = host.clientHeight;
        const v = this._tmpV || (this._tmpV = new this.THREE.Vector3());
        for (const l of this._labels) {
            v.copy(l.pos).project(this.camera);
            const hidden = v.z > 1;
            l.el.style.display = hidden ? "none" : "";
            if (!hidden) {
                l.el.style.transform = `translate(-50%, -100%) translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h}px)`;
            }
        }
    }

    _dispose() {
        this._destroyed = true;
        cancelAnimationFrame(this._raf);
        this._resizeObserver?.disconnect();
        this._io?.disconnect();
        if (this.renderer) {
            const el = this.renderer.domElement;
            el.removeEventListener("pointerdown", this._onDown);
            el.removeEventListener("pointermove", this._onMove);
            el.removeEventListener("pointerup", this._onUp);
            el.removeEventListener("pointerleave", this._onLeave);
            el.removeEventListener("wheel", this._onWheel);
            for (const d of new Set(this._disposables)) {
                d.dispose?.();
            }
            this.renderer.dispose();
            this.renderer.forceContextLoss?.();
            el.remove();
        }
    }
}
