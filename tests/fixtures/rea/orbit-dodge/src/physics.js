// Flight model + collision tests.
import { CONFIG } from "./config.js";

export function stepShip(ship, thrustY, dt) {
  ship.vy += (CONFIG.gravity + thrustY * CONFIG.thrust) * dt;
  ship.vx *= Math.pow(CONFIG.drag, dt);
  ship.vy *= Math.pow(CONFIG.drag, dt);
  const cap = CONFIG.maxSpeed;
  ship.vx = Math.max(-cap, Math.min(cap, ship.vx));
  ship.vy = Math.max(-cap, Math.min(cap, ship.vy));
  ship.x += ship.vx * dt;
  ship.y += ship.vy * dt;
  if (ship.x < 0) ship.x += CONFIG.width;
  if (ship.x > CONFIG.width) ship.x -= CONFIG.width;
  if (ship.y > CONFIG.height - CONFIG.shipRadius) {
    ship.y = CONFIG.height - CONFIG.shipRadius;
    ship.vy = Math.min(ship.vy, 0);
  }
  return ship;
}

export function circlesHit(ax, ay, ar, bx, by, br) {
  const dx = ax - bx;
  const dy = ay - by;
  const r = ar + br;
  return dx * dx + dy * dy <= r * r;
}

export function shipHitsAsteroid(ship, asteroid) {
  return circlesHit(ship.x, ship.y, CONFIG.shipRadius, asteroid.x, asteroid.y, CONFIG.asteroidRadius);
}
