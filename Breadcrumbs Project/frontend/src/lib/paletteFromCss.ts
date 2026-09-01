import * as THREE from 'three';

/**
 * The palette lives in `styles/tokens.css` and nowhere else.
 *
 * That rule is easy to keep in stylesheets and easy to break in a WebGL scene,
 * where colours are constructor arguments. This reads the tokens back off the
 * document at mount, so a three.js material and a CSS rule cannot drift apart.
 */
export function readPalette<K extends string>(tokens: Record<K, string>): Record<K, THREE.Color> {
  const style = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement)
    : null;

  const out = {} as Record<K, THREE.Color>;
  (Object.keys(tokens) as K[]).forEach((key) => {
    const value = style?.getPropertyValue(tokens[key]).trim();
    // A missing token is a bug, not a design decision: fall back to white so it
    // is obvious on screen rather than silently plausible.
    out[key] = value ? new THREE.Color(value) : new THREE.Color(1, 1, 1);
  });
  return out;
}
