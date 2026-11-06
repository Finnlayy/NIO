"""Deploy: Apollo wird versioniert gebaut, atomar umgeschaltet und ist ruecksetzbar.

``deploy/release_apollo.sh`` laeuft gegen ein Fake-``npm``: Es legt den Build so
an, wie ``next build`` es mit ``NIO_NEXT_DIST_DIR`` taete. Geprueft wird der
Vertrag, nicht Next selbst: Ein neuer Build beruehrt den aktiven Ordner nie, ein
kaputter Build wird nie aktiv, und der Rollback trifft das vorige Release.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from . import REPO_ROOT

RELEASE = REPO_ROOT / "deploy" / "release_apollo.sh"

FAKE_NPM = """#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "$NPM_LOG"
prefix="$2"; cmd="$3"
case "$cmd" in
  ci) mkdir -p "$prefix/node_modules" ;;
  run)
    [ "${FAKE_FAIL:-0}" = 1 ] && { mkdir -p "$prefix/$NIO_NEXT_DIST_DIR"; echo half > "$prefix/$NIO_NEXT_DIST_DIR/x"; exit 1; }
    mkdir -p "$prefix/$NIO_NEXT_DIST_DIR"
    [ "${FAKE_NO_BUILD_ID:-0}" = 1 ] || echo "build-$RANDOM" > "$prefix/$NIO_NEXT_DIST_DIR/BUILD_ID"
    ;;
esac
"""


def pointer(path: Path) -> str:
    return path.read_text().strip().removeprefix("NIO_NEXT_DIST_DIR=.releases/")


@unittest.skipUnless(shutil.which("bash") and shutil.which("sha256sum"), "bash/coreutils fehlen")
class ReleaseApolloTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.root = base / "repo"
        (self.root / "frontend").mkdir(parents=True)
        (self.root / "frontend" / "package-lock.json").write_text("{}")
        self.config = base / "config"
        self.releases = self.root / "frontend" / ".releases"
        self.npm = base / "npm"
        self.npm.write_text(FAKE_NPM)
        self.npm.chmod(0o755)
        self.log = base / "npm.log"
        self.env = {"PATH": os.environ["PATH"], "NPM": str(self.npm), "NPM_LOG": str(self.log)}

    def release(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(RELEASE), str(self.root), str(self.config), *args],
            env={**self.env, **env}, capture_output=True, text=True, timeout=60,
        )

    def active(self) -> str:
        return pointer(self.config / "apollo.release")

    def test_first_release_is_activated(self) -> None:
        proc = self.release()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rid = proc.stdout.strip().splitlines()[-1]
        self.assertEqual(self.active(), rid)
        self.assertTrue((self.releases / rid / "BUILD_ID").is_file())
        self.assertFalse((self.config / "apollo.release.previous").exists())

    def test_new_build_never_touches_the_active_release(self) -> None:
        first = self.release().stdout.strip()
        build_id = (self.releases / first / "BUILD_ID").read_text()
        second = self.release().stdout.strip()
        self.assertNotEqual(first, second)
        self.assertEqual(self.active(), second)
        self.assertEqual(pointer(self.config / "apollo.release.previous"), first)
        self.assertEqual((self.releases / first / "BUILD_ID").read_text(), build_id)

    def test_failed_build_is_never_activated(self) -> None:
        first = self.release().stdout.strip()
        for flag in ("FAKE_FAIL", "FAKE_NO_BUILD_ID"):
            proc = self.release(**{flag: "1"})
            self.assertNotEqual(proc.returncode, 0, flag)
            self.assertEqual(self.active(), first, flag)
            dirs = sorted(p.name for p in self.releases.iterdir() if p.is_dir())
            self.assertEqual(dirs, [first], f"halber Build liegen geblieben ({flag})")

    def test_rollback_switches_to_previous(self) -> None:
        first = self.release().stdout.strip()
        second = self.release().stdout.strip()
        proc = self.release("--rollback")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.active(), first)
        self.assertEqual(pointer(self.config / "apollo.release.previous"), second)

    def test_rollback_without_previous_fails_closed(self) -> None:
        first = self.release().stdout.strip()
        proc = self.release("--rollback")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.active(), first)

    def test_old_releases_are_pruned_but_active_and_previous_stay(self) -> None:
        ids = [self.release().stdout.strip() for _ in range(5)]
        self.release("--rollback")  # aktiv = ids[3], vorher = ids[4]
        ids.append(self.release().stdout.strip())
        dirs = {p.name for p in self.releases.iterdir() if p.is_dir()}
        self.assertEqual(len(dirs), 3, dirs)
        self.assertIn(self.active(), dirs)
        self.assertIn(pointer(self.config / "apollo.release.previous"), dirs)

    def test_npm_ci_only_when_lockfile_changes(self) -> None:
        self.release()
        self.release()
        self.assertEqual(self.log.read_text().count(" ci"), 1)
        (self.root / "frontend" / "package-lock.json").write_text('{"changed": true}')
        self.release()
        self.assertEqual(self.log.read_text().count(" ci"), 2)


class ApolloUnitReadsReleaseTests(unittest.TestCase):
    def test_unit_and_next_config_use_the_release_pointer(self) -> None:
        unit = (REPO_ROOT / "deploy" / "systemd" / "nio-apollo.service").read_text()
        self.assertIn("EnvironmentFile=%h/.config/nio/apollo.release", unit)
        config = (REPO_ROOT / "frontend" / "next.config.ts").read_text()
        self.assertIn("process.env.NIO_NEXT_DIST_DIR", config)
        install = (REPO_ROOT / "deploy" / "install.sh").read_text()
        self.assertNotIn("run build", install, "install.sh darf nicht mehr in den aktiven Build schreiben")


if __name__ == "__main__":
    unittest.main()
