import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useMemo, useRef, type MutableRefObject } from 'react';
import * as THREE from 'three';

import { readPalette } from '../lib/paletteFromCss';

/**
 * The constrained store.
 *
 * A database drawn the way every diagram draws one — a stack of platters — with
 * a chain wound around it. As the reader descends the limitations the wrap pays
 * out, one tier at a time, and each platter it releases takes a brass edge.
 *
 * Two things make it read as a chain rather than as beads. The links are placed
 * along a single continuous path at a fixed pitch shorter than their own
 * diameter, so consecutive links overlap and interlock; and their number is
 * conserved — unwinding moves links from the helix onto the fall and into the
 * heap, it never creates or destroys one. What is on the floor came off the
 * store.
 *
 * The chain never comes all the way off. The lowest turns stay wound however
 * far you scroll, because the section this belongs to is titled "what we cannot
 * do yet", and a wrap that fell away entirely would be telling a different, and
 * flattering, story. The constraint is the content.
 */

const TAU = Math.PI * 2;

const TIERS = 9;
const TIER_GAP = 0.62;
const R_DB = 1.72;
const DISC_H = 0.3;
const H = TIERS * TIER_GAP;

/** Link geometry. The pitch is under 2·major, which is what makes them link. */
const LR = 0.135;
const LT = 0.042;
const PITCH = LR * 1.4;
const R_WRAP = R_DB + LR + LT;

/** One turn of the wrap per limitation. */
const TOTAL_TURNS = TIERS;
/** Turns that stay wound at full progress. What is still binding us. */
const LOCKED_TURNS = 4;

const Y_HELIX = -H / 2;
const RISE = (H + 0.2) / TOTAL_TURNS;
const PER_TURN = Math.hypot(TAU * R_WRAP, RISE);
const LINKS = Math.round((TOTAL_TURNS * PER_TURN) / PITCH);

const GROUND = -H / 2 - 0.62;
const R_LAND = R_WRAP + 0.9;

/** How the heap spreads as more chain arrives: r = A + B·s. */
const PILE_A = 0.42;
const PILE_B = 0.024;

const LUT = 18;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

function Stack({ progress }: { progress: MutableRefObject<number> }) {
  const platters = useRef<THREE.InstancedMesh>(null);
  const rims = useRef<THREE.InstancedMesh>(null);
  const links = useRef<THREE.InstancedMesh>(null);
  const group = useRef<THREE.Group>(null);
  const { viewport } = useThree();

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const colour = useMemo(() => new THREE.Color(), []);

  const palette = useMemo(
    () => readPalette({
      bound: '--unbleached',
      freed: '--raw-cotton',
      rimBound: '--indigo-mid',
      rimFreed: '--brass',
      iron: '--thread-grey',
      slack: '--slub',
      fill: '--indigo-mid',
    }),
    [],
  );

  // Scratch. Nothing in the frame loop allocates.
  const s = useMemo(() => ({
    p0: new THREE.Vector3(), p1: new THREE.Vector3(), p2: new THREE.Vector3(),
    p3: new THREE.Vector3(), a: new THREE.Vector3(), b: new THREE.Vector3(),
    t: new THREE.Vector3(), n: new THREE.Vector3(), bi: new THREE.Vector3(),
    up: new THREE.Vector3(), x: new THREE.Vector3(), y: new THREE.Vector3(),
    z: new THREE.Vector3(),
    fall: new Float32Array(LUT + 1),
  }), []);

  useFrame((state) => {
    const p = clamp01(progress.current);
    const time = state.clock.elapsedTime;
    const spin = time * 0.05;

    const boundTurns = TOTAL_TURNS - p * (TOTAL_TURNS - LOCKED_TURNS);
    const boundLen = boundTurns * PER_TURN;

    /* -- the path ------------------------------------------------------- */
    const helixAt = (u: number, out: THREE.Vector3) => {
      const turns = u / PER_TURN;
      const ang = turns * TAU + spin;
      out.set(Math.cos(ang) * R_WRAP, Y_HELIX + turns * RISE, Math.sin(ang) * R_WRAP);
    };

    // Where the wrap ends and the slack begins, and which way it is heading.
    helixAt(boundLen, s.p0);
    helixAt(Math.max(0, boundLen - 0.08), s.a);
    s.t.copy(s.p0).sub(s.a).normalize();

    const relAng = (boundTurns * TAU + spin) % TAU;
    const landX = Math.cos(relAng) * R_LAND;
    const landZ = Math.sin(relAng) * R_LAND;

    // The fall: a cubic leaving the wrap tangentially and settling on the floor.
    s.p1.copy(s.p0).addScaledVector(s.t, 0.85);
    s.p3.set(landX, GROUND, landZ);
    s.p2.copy(s.p3).setY(GROUND + 1.15);

    const bezier = (w: number, out: THREE.Vector3) => {
      const m = 1 - w;
      out.set(0, 0, 0)
        .addScaledVector(s.p0, m * m * m)
        .addScaledVector(s.p1, 3 * m * m * w)
        .addScaledVector(s.p2, 3 * m * w * w)
        .addScaledVector(s.p3, w * w * w);
    };

    // Arc-length table, so links are evenly spaced down the fall rather than
    // bunching where the curve is slow.
    s.fall[0] = 0;
    bezier(0, s.a);
    for (let i = 1; i <= LUT; i += 1) {
      bezier(i / LUT, s.b);
      s.fall[i] = s.fall[i - 1] + s.a.distanceTo(s.b);
      s.a.copy(s.b);
    }
    const fallLen = s.fall[LUT];

    const pileAt = (dist: number, out: THREE.Vector3) => {
      // r grows with the length delivered, so the heap spreads instead of
      // stacking one ring on top of itself. θ integrates dθ = ds / r.
      const r = PILE_A + PILE_B * dist;
      const ang = relAng + 0.7 + Math.log(r / PILE_A) / PILE_B;
      const wobble = r + 0.16 * Math.sin(ang * 1.7) + 0.07 * Math.sin(ang * 0.6);
      out.set(
        landX * 0.78 + Math.cos(ang) * wobble,
        GROUND + Math.min(dist * 0.019, 0.46) + 0.05 * Math.sin(ang * 2.7),
        landZ * 0.78 + Math.sin(ang) * wobble,
      );
    };

    const pointAt = (u: number, out: THREE.Vector3) => {
      if (u <= boundLen) { helixAt(u, out); return; }
      const v = u - boundLen;
      if (v <= fallLen) {
        // Invert the table to get the curve parameter for this arc length.
        let i = 1;
        while (i < LUT && s.fall[i] < v) i += 1;
        const span = s.fall[i] - s.fall[i - 1] || 1;
        bezier((i - 1 + (v - s.fall[i - 1]) / span) / LUT, out);
        return;
      }
      pileAt(v - fallLen, out);
    };

    /* -- the platters --------------------------------------------------- */
    if (platters.current && rims.current) {
      for (let i = 0; i < TIERS; i += 1) {
        // Tiers unlock from the top down, one per admission — and only as many
        // as the wrap actually releases, so the platters and the chain tell the
        // same story: at full progress the lowest four are still bound.
        const unlocked = clamp01(p * (TIERS - LOCKED_TURNS) - (TIERS - 1 - i));
        const rank = i - (TIERS - 1) / 2;
        const y = rank * TIER_GAP + unlocked * 0.3 * rank * 0.5;

        dummy.position.set(0, y, 0);
        dummy.rotation.set(0, unlocked * 0.5 + time * 0.04, 0);
        dummy.scale.setScalar(1 + unlocked * 0.03);
        dummy.updateMatrix();
        platters.current.setMatrixAt(i, dummy.matrix);

        colour.copy(palette.bound).lerp(palette.freed, unlocked);
        platters.current.setColorAt(i, colour);

        // The freed signal is an edge, never a gilded body. Set the whole euler
        // rather than one axis: with the default XYZ order the spin would be
        // applied first and stand the ring on end.
        dummy.rotation.set(Math.PI / 2, 0, 0);
        dummy.updateMatrix();
        rims.current.setMatrixAt(i, dummy.matrix);
        colour.copy(palette.rimBound).lerp(palette.rimFreed, unlocked);
        rims.current.setColorAt(i, colour);
      }
      platters.current.instanceMatrix.needsUpdate = true;
      rims.current.instanceMatrix.needsUpdate = true;
      if (platters.current.instanceColor) platters.current.instanceColor.needsUpdate = true;
      if (rims.current.instanceColor) rims.current.instanceColor.needsUpdate = true;
    }

    /* -- the chain ------------------------------------------------------ */
    if (links.current) {
      for (let i = 0; i < LINKS; i += 1) {
        const u = i * PITCH;
        pointAt(u, s.a);
        pointAt(Math.max(0, u - 0.03), s.b);
        pointAt(u + 0.03, s.p1);
        s.t.copy(s.p1).sub(s.b);
        if (s.t.lengthSq() < 1e-8) s.t.set(1, 0, 0);
        s.t.normalize();

        // A frame that follows the path: the tangent lies in the ring's plane,
        // and consecutive links swap the other two axes to alternate by 90°.
        s.up.set(0, 1, 0);
        if (Math.abs(s.t.y) > 0.94) s.up.set(1, 0, 0);
        s.n.copy(s.t).cross(s.up).normalize();
        s.bi.copy(s.n).cross(s.t).normalize();

        s.x.copy(s.t);
        if (i % 2) { s.y.copy(s.n); s.z.copy(s.bi).negate(); }
        else { s.y.copy(s.bi); s.z.copy(s.n); }

        dummy.matrix.makeBasis(s.x, s.y, s.z);
        dummy.matrix.setPosition(s.a);
        links.current.setMatrixAt(i, dummy.matrix);

        // Slack chain is spent: it cools as it leaves the wrap, without
        // disappearing into the ground it is lying on.
        colour.copy(palette.iron);
        if (u > boundLen) colour.lerp(palette.slack, 0.55);
        links.current.setColorAt(i, colour);
      }
      links.current.instanceMatrix.needsUpdate = true;
      if (links.current.instanceColor) links.current.instanceColor.needsUpdate = true;
    }

    if (group.current) {
      // The canvas is bounded to the clear field by CSS, so the stack fills its
      // own box rather than being nudged in world units.
      group.current.scale.setScalar(Math.min(0.95, Math.max(0.48, viewport.width / 8.1)));
      group.current.rotation.y = time * 0.07;
      group.current.rotation.x = -0.24;
      group.current.position.y = 0.34;
    }
  });

  return (
    <group ref={group}>
      <instancedMesh ref={platters} args={[undefined, undefined, TIERS]} frustumCulled={false}>
        <cylinderGeometry args={[R_DB, R_DB, DISC_H, 60, 1]} />
        <meshStandardMaterial roughness={0.78} metalness={0.04} toneMapped={false} />
      </instancedMesh>

      <instancedMesh ref={rims} args={[undefined, undefined, TIERS]} frustumCulled={false}>
        <torusGeometry args={[R_DB + 0.015, 0.038, 6, 60]} />
        <meshStandardMaterial roughness={0.4} metalness={0.6} toneMapped={false} />
      </instancedMesh>

      <instancedMesh ref={links} args={[undefined, undefined, LINKS]} frustumCulled={false}>
        <torusGeometry args={[LR, LT, 6, 14]} />
        <meshStandardMaterial roughness={0.38} metalness={0.8} toneMapped={false} />
      </instancedMesh>
    </group>
  );
}

export default function ChainedStack({ progress }: { progress: MutableRefObject<number> }) {
  const fill = useMemo(() => readPalette({ c: '--indigo-mid' }).c, []);

  return (
    <Canvas
      dpr={[1, 1.7]}
      camera={{ position: [0, 0.4, 12], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      style={{ position: 'absolute', inset: 0 }}
    >
      {/* Neutral key, cool fill. A warm key was half of why cream read as gold. */}
      <ambientLight intensity={0.62} />
      <directionalLight position={[-5, 7, 6]} intensity={0.88} />
      <directionalLight position={[6, -3, 4]} intensity={0.4} color={fill} />
      <Stack progress={progress} />
    </Canvas>
  );
}
