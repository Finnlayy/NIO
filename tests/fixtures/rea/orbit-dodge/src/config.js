// Orbit Dodge -- tunables. The scoring constants are the part worth recovering.
export const CONFIG = {
  width: 480,
  height: 640,
  gravity: 0.28,
  thrust: 0.55,
  drag: 0.992,
  maxSpeed: 6.5,
  shipRadius: 9,
  asteroidRadius: 14,
  spawnEveryMs: 900,
  comboWindowMs: 1400,
  comboStep: 0.35,
  maxCombo: 5,
  startLives: 3,
};

export const PHASE = {
  MENU: "menu",
  RUNNING: "running",
  PAUSED: "paused",
  OVER: "over",
};
