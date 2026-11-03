# J12: Pin google-genai in Architect (NIO)

Branch: `jules/j12-genai-pin`

Files: `Architect/requirements.txt`, `Architect/limbs/intelligence/genai_client.py`, tests under `Architect/tests/`.

## Gaps

- `google-genai` is not pinned to an exact version.
- Automatic function calling is not set explicitly.
- A plan names an LM Studio fallback in `genai_client.py`, but it could not be found there.

## Required result

- `google-genai` is pinned to one exact version, the one the code already works with. Say in the PR how you chose it.
- `genai_client.py` sets function calling explicitly, so no tool is called automatically.
- Check whether an LM Studio fallback exists anywhere in `Architect/`. State the result in the PR with file references. If there is none, do not add one.
- Tests cover the explicit setting without network access.
- `awesome-opencode` stays out of this PR. Add no plugins.

The rule about standard library only applies to the NIO core, not to `Architect/`, which already has `requirements.txt`. Add no new package.
