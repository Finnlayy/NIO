import os
import unittest
from pathlib import Path

import sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from limbs.container import ContainerConfig, build_docker_run_args, ConfigError

class TestContainer(unittest.TestCase):
    def setUp(self):
        self.run_dir = _REPO_ROOT / "runtime" / "agents" / "test_run_123"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.valid_mount = self.run_dir / "workspace"
        self.valid_mount.mkdir(parents=True, exist_ok=True)

    def test_build_docker_run_args_success(self):
        config = ContainerConfig(
            name="test_container",
            image="test_image",
            run_dir=self.run_dir,
            agent_name="test_agent",
            mounts={self.valid_mount: "/app/workspace"},
            env={"TEST_KEY": "TEST_VAL"},
            tmpfs=["/tmp,size=64m"]
        )
        args, env = build_docker_run_args(config)
        self.assertEqual(args[0], "run")
        self.assertIn("--read-only", args)
        self.assertIn("--cap-drop", args)
        self.assertIn("ALL", args)
        self.assertIn("--security-opt", args)
        self.assertIn("no-new-privileges", args)
        self.assertIn("--rm", args)
        self.assertIn("--volume", args)
        self.assertIn(f"{self.valid_mount.resolve()}:/app/workspace", args)

        # Test Env is split
        self.assertIn("--env", args)
        self.assertIn("TEST_KEY", args)
        self.assertNotIn("TEST_KEY=TEST_VAL", args)
        self.assertEqual(env["TEST_KEY"], "TEST_VAL")

        self.assertIn("--tmpfs", args)
        self.assertIn("/tmp,size=64m", args)
        self.assertEqual(args[-1], "test_image")

    def test_refuse_docker_sock(self):
        bad_mount = Path("/var/run/docker.sock")
        config = ContainerConfig(
            name="test_container",
            image="test_image",
            run_dir=self.run_dir,
            agent_name="test_agent",
            mounts={bad_mount: "/var/run/docker.sock"}
        )
        with self.assertRaisesRegex(ConfigError, "docker.sock Mount ist verboten."):
            build_docker_run_args(config)

    def test_refuse_workspace(self):
        workspace = _REPO_ROOT / "workspace"
        config = ContainerConfig(
            name="test_container",
            image="test_image",
            run_dir=self.run_dir,
            agent_name="test_agent",
            mounts={workspace: "/app/workspace"}
        )
        with self.assertRaisesRegex(ConfigError, "workspace/ Mount ist verboten."):
            build_docker_run_args(config)

    def test_refuse_outside_run_dir(self):
        outside_dir = _REPO_ROOT / "runtime" / "agents" / "other_run_dir"
        outside_dir.mkdir(parents=True, exist_ok=True)
        config = ContainerConfig(
            name="test_container",
            image="test_image",
            run_dir=self.run_dir,
            agent_name="test_agent",
            mounts={outside_dir: "/app/workspace"}
        )
        with self.assertRaisesRegex(ConfigError, "liegt ausserhalb des run_dir"):
            build_docker_run_args(config)

    def test_refuse_repo_root(self):
        config = ContainerConfig(
            name="test_container",
            image="test_image",
            run_dir=self.run_dir,
            agent_name="test_agent",
            mounts={_REPO_ROOT: "/app/repo"}
        )
        with self.assertRaisesRegex(ConfigError, "Repo Root Mount ist verboten."):
            build_docker_run_args(config)

    def test_refuse_home(self):
        home = os.environ.get("HOME")
        if home:
            config = ContainerConfig(
                name="test_container",
                image="test_image",
                run_dir=self.run_dir,
                agent_name="test_agent",
                mounts={Path(home): "/root"}
            )
            with self.assertRaisesRegex(ConfigError, "\\$HOME Mount ist verboten."):
                build_docker_run_args(config)

    def test_run_dir_out_of_bounds(self):
        # run_dir out of runtime/agents
        bad_run_dir = _REPO_ROOT / "runtime" / "inbox" / "123"
        config = ContainerConfig(
            name="t", image="i", agent_name="a", run_dir=bad_run_dir
        )
        with self.assertRaisesRegex(ConfigError, "muss innerhalb von"):
            build_docker_run_args(config)

    def test_run_dir_root(self):
        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=Path("/"))
        with self.assertRaisesRegex(ConfigError, "run_dir / ist verboten"):
            build_docker_run_args(config)

    def test_refuse_colon_in_mount(self):
        bad_mount = self.run_dir / "foo:bar"
        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, mounts={bad_mount: "/foo"})
        with self.assertRaisesRegex(ConfigError, "Doppelpunkt"):
            build_docker_run_args(config)

        config2 = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, mounts={self.valid_mount: "/foo:bar"})
        with self.assertRaisesRegex(ConfigError, "Doppelpunkt"):
            build_docker_run_args(config2)

    def test_network_validation(self):
        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, network="host")
        with self.assertRaisesRegex(ConfigError, "Netzwerk host ist verboten"):
            build_docker_run_args(config)

        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, network="none")
        args, _ = build_docker_run_args(config)
        self.assertIn("--network", args)

    def test_uid_validation(self):
        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, user="0:0")
        with self.assertRaisesRegex(ConfigError, "User oder Gruppe root"):
            build_docker_run_args(config)

        for user in ("root:root", "ROOT", "1000:0", "1000:root"):
            config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, user=user)
            with self.assertRaises(ConfigError):
                build_docker_run_args(config)
        config = ContainerConfig(name="t", image="i", agent_name="a", run_dir=self.run_dir, user="root")
        with self.assertRaisesRegex(ConfigError, "User oder Gruppe root"):
            build_docker_run_args(config)

if __name__ == '__main__':
    unittest.main()
