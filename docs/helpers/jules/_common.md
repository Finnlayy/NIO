
## Rules for this task

- Base: `main`. Work on the branch named above and open one pull request into `main`. Do not merge it.
- Other agents change other files in parallel. Touch only the files listed above and the tests that belong to them. If you truly need another file, keep the change minimal and name it in the PR.
- Do not change `.github/`, `neu.config.json`, `core/config.py`, or anything under `workspace/`.
- Write a test for each gap first. It must fail before the fix and pass after it. Say in the PR that you saw both.
- The Python core uses only the standard library. Add no dependencies. Match the surrounding naming, comments and German messages.
- Fail closed: if a check cannot run, deny.
- Never put secrets into code, tests, logs or examples.
- Tests that encode the old hole may be changed. List each one in the PR with the reason.
- Run the related tests and `make lint` before you finish. Report exactly what you ran, its result, and what you could not run (for example Docker).
- Do not stop to ask questions. Choose the safer option and record the assumption in the PR.
