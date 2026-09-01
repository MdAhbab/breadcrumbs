import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useMemo, useRef, type MutableRefObject } from 'react';
import * as THREE from 'three';

/**
 * The weave.
 *
 * A Merkle tree and a woven fabric are the same structure: threads interlace in
 * pairs, those pairs interlace again, until the whole thing is one bolt of
 * cloth — and a single thread can be traced through it without unravelling the
 * rest. That is selective disclosure, and it is also weaving.
 *
 * This scene holds ~2,300 thread segments in one InstancedMesh and moves them
 * between three states, driven entirely by scroll position:
 *
 *   0.0 → 0.33   loose      scattered in space, drifting
 *   0.33 → 0.66  woven      warp and weft interlaced into a plane
 *   0.66 → 1.0   traced     one thread lifts out; its proof path lights up
 *
 * Everything is interpolation between precomputed target transforms. No physics,
 * no per-frame allocation, one draw call.
 */

const GRID = 34; // warp count; total threads ≈ GRID * GRID * 2
const SPAN = 13;
const CELL = SPAN / GRID;

interface ThreadTargets {
  loose: Float32Array;   // xyz per instance
  looseRot: Float32Array;
  woven: Float32Array;
  wovenRot: Float32Array;
  lift: Float32Array;    // the traced thread's raised position
  isTraced: Uint8Array;
  isSibling: Uint8Array;
  count: number;
}

function buildTargets(): ThreadTargets {
  const perAxis = GRID * GRID;
  const count = perAxis * 2;

  const loose = new Float32Array(count * 3);
  const looseRot = new Float32Array(count * 3);
  const woven = new Float32Array(count * 3);
  const wovenRot = new Float32Array(count * 3);
  const lift = new Float32Array(count * 3);
  const isTraced = new Uint8Array(count);
  const isSibling = new Uint8Array(count);

  // The thread we will trace, and the eleven siblings on its path to the root.
  const tracedRow = Math.floor(GRID * 0.42);
  const tracedCol = Math.floor(GRID * 0.56);
  const siblingCols = new Set<number>();
  for (let level = 0, span = 1; level < 11; level += 1, span *= 2) {
    siblingCols.add((tracedCol + span) % GRID);
  }

  let i = 0;
  const place = (
    x: number, y: number, z: number,
    rx: number, ry: number, rz: number,
    traced: boolean, sibling: boolean,
  ) => {
    // Loose: scattered through a wide, shallow volume.
    const a = Math.random() * Math.PI * 2;
    const r = 5 + Math.random() * 11;
    loose[i * 3] = Math.cos(a) * r;
    loose[i * 3 + 1] = (Math.random() - 0.5) * 13;
    loose[i * 3 + 2] = Math.sin(a) * r * 0.55 - 3;
    looseRot[i * 3] = Math.random() * Math.PI;
    looseRot[i * 3 + 1] = Math.random() * Math.PI;
    looseRot[i * 3 + 2] = Math.random() * Math.PI;

    woven[i * 3] = x;
    woven[i * 3 + 1] = y;
    woven[i * 3 + 2] = z;
    wovenRot[i * 3] = rx;
    wovenRot[i * 3 + 1] = ry;
    wovenRot[i * 3 + 2] = rz;

    // The traced thread lifts toward the camera; siblings rise a little.
    lift[i * 3] = x;
    lift[i * 3 + 1] = y;
    lift[i * 3 + 2] = z + (traced ? 2.6 : sibling ? 0.75 : 0);

    isTraced[i] = traced ? 1 : 0;
    isSibling[i] = sibling ? 1 : 0;
    i += 1;
  };

  // Warp: vertical threads.
  for (let c = 0; c < GRID; c += 1) {
    for (let s = 0; s < GRID; s += 1) {
      const x = (c - GRID / 2) * CELL;
      const y = (s - GRID / 2) * CELL;
      // Over-under: the interlace that makes it cloth rather than a grid.
      const z = (c + s) % 2 === 0 ? 0.09 : -0.09;
      place(x, y, z, 0, 0, Math.PI / 2, false, false);
    }
  }

  // Weft: horizontal threads.
  for (let r = 0; r < GRID; r += 1) {
    for (let s = 0; s < GRID; s += 1) {
      const x = (s - GRID / 2) * CELL;
      const y = (r - GRID / 2) * CELL;
      const z = (r + s) % 2 === 0 ? -0.09 : 0.09;
      const traced = r === tracedRow && s === tracedCol;
      const sibling = r === tracedRow && siblingCols.has(s);
      place(x, y, z, 0, 0, 0, traced, sibling);
    }
  }

  return { loose, looseRot, woven, wovenRot, lift, isTraced, isSibling, count };
}

const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

function Threads({ progress }: { progress: MutableRefObject<number> }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const targets = useMemo(buildTargets, []);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const colour = useMemo(() => new THREE.Color(), []);
  const { viewport } = useThree();

  // Colours are set once per state change rather than per frame where possible.
  // These are lit values, not surface values: the mesh is unlit-ish at this
  // scale, so the colours carry most of the contrast themselves.
  const base = useMemo(() => new THREE.Color('#8296bd'), []);
  const brass = useMemo(() => new THREE.Color('#e8c47d'), []);
  const dim = useMemo(() => new THREE.Color('#2b3a58'), []);

  useFrame((state) => {
    const m = mesh.current;
    if (!m) return;

    const p = clamp01(progress.current);
    // Phase 1: loose → woven. Phase 2: woven → traced.
    const weave = easeInOut(clamp01(p / 0.62));
    const trace = easeInOut(clamp01((p - 0.62) / 0.38));
    const t = state.clock.elapsedTime;

    for (let i = 0; i < targets.count; i += 1) {
      const o = i * 3;

      // Loose threads drift; woven ones are still.
      const drift = (1 - weave) * 0.55;
      const lx = targets.loose[o] + Math.sin(t * 0.28 + i) * drift;
      const ly = targets.loose[o + 1] + Math.cos(t * 0.23 + i * 0.7) * drift;
      const lz = targets.loose[o + 2];

      const wx = targets.woven[o];
      const wy = targets.woven[o + 1];
      const wz = targets.woven[o + 2];

      // Then, in phase two, the traced thread and its siblings lift out.
      const tx = targets.lift[o];
      const ty = targets.lift[o + 1];
      const tz = targets.lift[o + 2];

      const px = lx + (wx - lx) * weave;
      const py = ly + (wy - ly) * weave;
      const pz = lz + (wz - lz) * weave;

      dummy.position.set(
        px + (tx - px) * trace,
        py + (ty - py) * trace,
        pz + (tz - pz) * trace,
      );

      dummy.rotation.set(
        targets.looseRot[o] + (targets.wovenRot[o] - targets.looseRot[o]) * weave,
        targets.looseRot[o + 1] + (targets.wovenRot[o + 1] - targets.looseRot[o + 1]) * weave,
        targets.looseRot[o + 2] + (targets.wovenRot[o + 2] - targets.looseRot[o + 2]) * weave,
      );

      // The traced thread thickens as it lifts, so the eye finds it.
      const traced = targets.isTraced[i] === 1;
      const sibling = targets.isSibling[i] === 1;
      const scale = traced ? 1 + trace * 3.2 : sibling ? 1 + trace * 1.1 : 1;
      dummy.scale.set(scale, 1, scale);

      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);

      // Colour: everything settles to indigo, then the proof path lights brass
      // and the rest of the cloth dims — visibly redacted.
      if (traced) {
        colour.copy(base).lerp(brass, Math.max(weave * 0.3, trace));
      } else if (sibling) {
        colour.copy(base).lerp(brass, trace * 0.8);
      } else {
        colour.copy(base).lerp(dim, trace * 0.75);
      }
      m.setColorAt(i, colour);
    }

    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;

    // The plane turns slowly toward flat-on as it weaves, so the trace reads.
    // Wide viewports put the cloth in the clear right-hand field, beside the
    // copy. Narrow ones centre it, because there is no clear field to move to.
    const wide = viewport.aspect > 1.15;
    const scale = Math.min(1.05, viewport.width / 13);
    m.position.x = wide ? viewport.width * 0.2 : 0;
    m.position.y = 0;
    m.rotation.x = (1 - weave) * 0.35 + Math.sin(t * 0.12) * 0.045 * (1 - trace);
    m.rotation.y = (1 - weave) * -0.5 + Math.cos(t * 0.1) * 0.06 * (1 - trace);
    m.scale.setScalar(scale);
  });

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, targets.count]}
      frustumCulled={false}
    >
      {/* A thread: long, thin, square section. Cheap and reads as fibre. */}
      <boxGeometry args={[0.035, CELL * 0.98, 0.035]} />
      <meshStandardMaterial roughness={0.5} metalness={0.35} toneMapped={false} />
    </instancedMesh>
  );
}

export default function WeaveScene({ progress }: { progress: MutableRefObject<number> }) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 15], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      style={{ position: 'absolute', inset: 0 }}
    >
      <ambientLight intensity={1.15} />
      {/* Brass rim from upper left — the loom-hardware light. */}
      <directionalLight position={[-6, 8, 7]} intensity={2.6} color="#e8c47d" />
      <directionalLight position={[7, -4, 4]} intensity={1.3} color="#6d8ecb" />
      <Threads progress={progress} />
    </Canvas>
  );
}
