// Headless game engine: same code the browser build runs, minus the canvas.
import { CONFIG, PHASE } from "./config.js";
import { mulberry32, pickInt } from "./rng.js";
import { stepShip, shipHitsAsteroid } from "./physics.js";
import { awardDodge, createScoreState, penalty, finalScore } from "./scoring.js";

export function createGame(seed = 1337) {
  return {
    seed,
    rng: mulberry32(seed),
    phase: PHASE.RUNNING,
    clockMs: 0,
    ship: { x: CONFIG.width / 2, y: CONFIG.height - 80, vx: 0, vy: 0 },
    asteroids: [],
    score: createScoreState(),
    lives: CONFIG.startLives,
    nextSpawnMs: 0,
    events: [],
  };
}

export function spawnAsteroid(game) {
  const asteroid = {
    id: game.asteroids.length + 1,
    x: pickInt(game.rng, 20, CONFIG.width - 20),
    y: -CONFIG.asteroidRadius,
    vy: 1.4 + game.rng() * 1.6,
    dodged: false,
  };
  game.asteroids.push(asteroid);
  return asteroid;
}

export function tick(game, dt, thrustY = 0) {
  if (game.phase !== PHASE.RUNNING) return game;
  game.clockMs += dt * 16.6667;

  if (game.clockMs >= game.nextSpawnMs) {
    spawnAsteroid(game);
    game.nextSpawnMs = game.clockMs + CONFIG.spawnEveryMs;
  }

  stepShip(game.ship, thrustY, dt);

  for (const asteroid of game.asteroids) {
    asteroid.y += asteroid.vy * dt;
    if (!asteroid.dodged && asteroid.y > game.ship.y + CONFIG.asteroidRadius) {
      asteroid.dodged = true;
      const gained = awardDodge(game.score, game.clockMs);
      game.events.push({ type: "dodge", id: asteroid.id, gained, at: Math.round(game.clockMs) });
    }
    if (shipHitsAsteroid(game.ship, asteroid)) {
      game.lives -= 1;
      penalty(game.score);
      game.events.push({ type: "hit", id: asteroid.id, at: Math.round(game.clockMs) });
      asteroid.y = CONFIG.height + 64;
      if (game.lives <= 0) {
        game.phase = PHASE.OVER;
      }
    }
  }
  game.asteroids = game.asteroids.filter((a) => a.y < CONFIG.height + 64);
  return game;
}

export function runSimulation(seed, frames = 1200) {
  const game = createGame(seed);
  for (let frame = 0; frame < frames && game.phase === PHASE.RUNNING; frame += 1) {
    // Cheap bot: thrust up whenever the nearest asteroid is close.
    const nearest = game.asteroids
      .filter((a) => a.y < game.ship.y)
      .sort((a, b) => b.y - a.y)[0];
    const thrust = nearest && Math.abs(nearest.x - game.ship.x) < 40 ? -1 : 0;
    tick(game, 1, thrust);
  }
  return {
    seed: game.seed,
    frames,
    score: game.score.points,
    final: finalScore(game.score),
    dodged: game.score.dodged,
    combo: game.score.combo,
    lives: game.lives,
    phase: game.phase,
    events: game.events.length,
  };
}
