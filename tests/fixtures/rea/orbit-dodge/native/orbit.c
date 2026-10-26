/*
 * Orbit Dodge -- native twin of the JavaScript fixture.
 *
 * The point of this file is not the game. It is that the same scoring rules the
 * JS bundle uses also exist in a stripped ELF, so a reverse-engineering pass on
 * the binary has something to find: the combo window, the step size, the dodge
 * payout, the penalty and the final-score correction.
 *
 * Build (the committed binary was produced with exactly this line):
 *   gcc -O2 -std=c11 -s -o native/orbit-game native/orbit.c
 *
 * Run:
 *   ./native/orbit-game 42 900      -> JSON line: score, final, dodged, combo
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIDTH 480
#define HEIGHT 640
#define GRAVITY 0.28
#define THRUST 0.55
#define DRAG 0.992
#define MAX_SPEED 6.5
#define SHIP_RADIUS 9
#define ASTEROID_RADIUS 14
#define SPAWN_EVERY_MS 900
#define COMBO_WINDOW_MS 1400
#define COMBO_STEP 0.35
#define MAX_COMBO 5
#define START_LIVES 3
#define DODGE_POINTS 10
#define PENALTY_POINTS 25
#define FINAL_BONUS_DIVISOR 100

typedef struct {
    double x, y, vx, vy;
} ship_t;

typedef struct {
    int id;
    double x, y, vy;
    int dodged;
} asteroid_t;

typedef struct {
    int points;
    int combo;
    double last_dodge_ms;
    double multiplier;
    int dodged;
} score_t;

static const char *BANNER = "ORBIT-DODGE/1 native-edition";

static uint32_t mulberry32(uint32_t *state) {
    uint32_t a = (*state += 0x6d2b79f5u);
    uint32_t t = a;
    t = (t ^ (t >> 15)) * (t | 1u);
    t ^= t + (t ^ (t >> 7)) * (t | 61u);
    return (t ^ (t >> 14));
}

static double frand(uint32_t *state) {
    return (double)mulberry32(state) / 4294967296.0;
}

static int pick_int(uint32_t *state, int min, int max) {
    return min + (int)(frand(state) * (double)(max - min + 1));
}

static double combo_multiplier(int combo) {
    int capped = combo < MAX_COMBO ? combo : MAX_COMBO;
    return 1.0 + (double)capped * COMBO_STEP;
}

static int award_dodge(score_t *s, double now_ms) {
    double elapsed = now_ms - s->last_dodge_ms;
    if (s->dodged == 0 || elapsed > (double)COMBO_WINDOW_MS) {
        s->combo = 1;
    } else {
        int next = s->combo + 1;
        s->combo = next < (MAX_COMBO + 1) ? next : (MAX_COMBO + 1);
    }
    s->last_dodge_ms = now_ms;
    s->dodged += 1;
    s->multiplier = combo_multiplier(s->combo);
    int gained = (int)((double)DODGE_POINTS * s->multiplier + 0.5);
    s->points += gained;
    return gained;
}

static void penalty(score_t *s) {
    s->combo = 0;
    s->multiplier = 1.0;
    s->points -= PENALTY_POINTS;
    if (s->points < 0) {
        s->points = 0;
    }
}

static int final_score(const score_t *s) {
    return (int)((double)s->points * (1.0 + (double)s->dodged / (double)FINAL_BONUS_DIVISOR) + 0.5);
}

int main(int argc, char **argv) {
    uint32_t seed = (argc > 1) ? (uint32_t)strtoul(argv[1], NULL, 10) : 1337u;
    int frames = (argc > 2) ? atoi(argv[2]) : 1200;
    uint32_t state = seed;

    ship_t ship = {WIDTH / 2.0, HEIGHT - 80.0, 0.0, 0.0};
    score_t score = {0, 0, 0.0, 1.0, 0};
    asteroid_t rocks[64];
    int rock_count = 0;
    int lives = START_LIVES;
    double clock_ms = 0.0;
    double next_spawn_ms = 0.0;
    int events = 0;

    for (int frame = 0; frame < frames && lives > 0; frame++) {
        clock_ms += 16.6667;
        if (clock_ms >= next_spawn_ms && rock_count < 64) {
            asteroid_t *rock = &rocks[rock_count++];
            rock->id = rock_count;
            rock->x = (double)pick_int(&state, 20, WIDTH - 20);
            rock->y = -(double)ASTEROID_RADIUS;
            rock->vy = 1.4 + frand(&state) * 1.6;
            rock->dodged = 0;
            next_spawn_ms = clock_ms + (double)SPAWN_EVERY_MS;
        }

        /* Cheap bot: push up when the nearest rock is close in x. */
        double thrust = 0.0;
        for (int i = 0; i < rock_count; i++) {
            if (rocks[i].y < ship.y) {
                double dx = rocks[i].x - ship.x;
                if (dx < 40.0 && dx > -40.0) {
                    thrust = -1.0;
                    break;
                }
            }
        }

        ship.vy += (GRAVITY + thrust * THRUST);
        ship.vx *= DRAG;
        ship.vy *= DRAG;
        if (ship.vx > MAX_SPEED) ship.vx = MAX_SPEED;
        if (ship.vx < -MAX_SPEED) ship.vx = -MAX_SPEED;
        if (ship.vy > MAX_SPEED) ship.vy = MAX_SPEED;
        if (ship.vy < -MAX_SPEED) ship.vy = -MAX_SPEED;
        ship.x += ship.vx;
        ship.y += ship.vy;
        if (ship.y > HEIGHT - SHIP_RADIUS) {
            ship.y = HEIGHT - SHIP_RADIUS;
            if (ship.vy > 0) ship.vy = 0;
        }

        for (int i = 0; i < rock_count; i++) {
            asteroid_t *rock = &rocks[i];
            rock->y += rock->vy;
            if (!rock->dodged && rock->y > ship.y + (double)ASTEROID_RADIUS) {
                rock->dodged = 1;
                award_dodge(&score, clock_ms);
                events++;
            }
            double dx = ship.x - rock->x;
            double dy = ship.y - rock->y;
            double reach = (double)(SHIP_RADIUS + ASTEROID_RADIUS);
            if (dx * dx + dy * dy <= reach * reach) {
                lives -= 1;
                penalty(&score);
                events++;
                rock->y = (double)HEIGHT + 64.0;
            }
        }

        int kept = 0;
        for (int i = 0; i < rock_count; i++) {
            if (rocks[i].y < (double)HEIGHT + 64.0) {
                rocks[kept++] = rocks[i];
            }
        }
        rock_count = kept;
    }

    printf("{\"seed\": %u, \"frames\": %d, \"score\": %d, \"final\": %d, \"dodged\": %d, "
           "\"combo\": %d, \"lives\": %d, \"events\": %d, \"banner\": \"%s\"}\n",
           seed, frames, score.points, final_score(&score), score.dodged, score.combo,
           lives, events, BANNER);
    return 0;
}
