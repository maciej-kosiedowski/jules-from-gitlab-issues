import subprocess
import sys
import time
import os


def test_main_script():
    # Run the main script as a subprocess and kill it after a second
    # This should cover the if __name__ == "__main__": block
    env = os.environ.copy()
    env.update(
        {
            "GITLAB_TOKEN": "test",
            "GITLAB_PROJECT_ID": "1",
            "GITHUB_TOKEN": "test",
            "GITHUB_REPO": "a/b",
            "JULES_API_KEY": "test",
            "POLLING_INTERVAL": "1",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "src.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    process.terminate()
