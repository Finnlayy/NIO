// Browser entry: canvas render loop around the shared engine.
import { CONFIG, PHASE } from "./config.js";
import { createGame, tick } from "./engine.js";
import { finalScore } from "./scoring.js";

export function mount(canvas, seed = 20260101) {
  const ctx = canvas.getContext("2d");
  canvas.width = CONFIG.width;
  canvas.height = CONFIG.height;
  let game = createGame(seed);
  let thrust = 0;

  canvas.addEventListener("pointerdown", () => {
    throttle(true);
  });
  canvas.addEventListener("pointerup", () => {
    throttle(false);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "ArrowUp" || event.key === " ") throttle(true);
    if (event.key === "r" && game.phase === PHASE.OVER) game = createGame(seed);
  });
  window.addEventListener("keyup", (event) => {
    if (event.key === "ArrowUp" || event.key === " ") throttle(false);
  });

  function throttle(on) {
    thrust = on ? -1 : 0;
  }

  function draw() {
    ctx.fillStyle = "#05070d";
    ctx.fillRect(0, 0, CONFIG.width, CONFIG.height);
    ctx.fillStyle = "#6ee7ff";
    ctx.beginPath();
    ctx.arc(game.ship.x, game.ship.y, CONFIG.shipRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f97316";
    for (const asteroid of game.asteroids) {
      ctx.beginPath();
      ctx.arc(asteroid.x, asteroid.y, CONFIG.asteroidRadius, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "16px ui-monospace, monospace";
    ctx.fillText(`score ${finalScore(game.score)}  combo x${game.score.multiplier.toFixed(2)}  lives ${game.lives}`, 16, 28);
    if (game.phase === PHASE.OVER) {
      ctx.fillText("game over -- press r", 16, 52);
    }
  }

  let last = 0;
  function loop(now) {
    const dt = last ? Math.min(2, (now - last) / 16.6667) : 1;
    last = now;
    tick(game, dt, thrust);
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
  return { get game() { return game; } };
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.OrbitDodge = { mount };
}
