# Fixture: Orbit Dodge

A small, fully deterministic game in three forms. It exists so the REA subagent
has something whose *correct* answer is known: evidence can be checked against
ground truth instead of against a plausible-looking summary.

```
src/        readable sources (the ground truth a human would start from)
app/        the shipped bundle: minified JS + page, what the subagent analyses
native/     orbit.c + a stripped ELF built from it, for the binary provider
```

## Provenance of the generated files

Both generated artefacts are committed on purpose: the acceptance gates must run
without a JS build toolchain and without a compiler.

| File | How it was produced |
|---|---|
| `app/game.min.js`, `app/cli.cjs` | `npx esbuild@0.25.10 <bundle> --minify --target=es2020 --legal-comments=none` |
| `native/orbit-game` | `gcc -O2 -std=c11 -s -o native/orbit-game native/orbit.c` |

`native/orbit-game` is a Linux x86_64 ELF (14 496 B, stripped,
`sha256 1bcbf6e51275597c…`). It is marked `binary` in `.gitattributes` so no
line-ending normalisation can ever touch it. Rebuild it with the line above if
you are on another platform; `native_check()` in
[`scripts/rea_recover_orbit.py`](../../../scripts/rea_recover_orbit.py) skips the
native comparison when the binary is missing or cannot execute, so a foreign
platform degrades to the JavaScript gate instead of failing.

## Determinism

The game is a pure function of `(seed, frames)`. Both interfaces take those two
arguments and print one JSON line:

```bash
node app/cli.cjs 42 900
./native/orbit-game 42 900
```

That is what makes the differential test in `scripts/rea_recover_orbit.py`
meaningful: a reconstruction is accepted only if it reproduces
`score`, `final`, `dodged`, `combo`, `lives`, `phase` and the event count for
every seed/frame pair in the gate.
