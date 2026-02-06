import gitlab
from src.config import settings
from src.utils.logger import logger

class GitLabClient:
    def __init__(self):
        self.gl = gitlab.Gitlab(settings.GITLAB_URL, private_token=settings.GITLAB_TOKEN)
        self.project = self.gl.projects.get(settings.GITLAB_PROJECT_ID)

    def get_open_ai_issues(self):
        """Fetch open issues with 'AI' label."""
        return self.project.issues.list(state="opened", labels=["AI"])

    def create_merge_request(self, source_branch: str, target_branch: str, title: str, description: str):
        """Create a Merge Request in GitLab."""
        return self.project.mergerequests.create({
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description
        })

    def has_open_mr(self, issue_iid: int) -> bool:
        """Check if an issue has any open Merge Requests."""
        try:
            issue = self.project.issues.get(issue_iid)
            mrs = issue.related_merge_requests()
            return any(mr["state"] == "opened" for mr in mrs)
        except Exception as e:
            logger.error(f"Error checking open MRs for issue {issue_iid}: {e}")
            return False

    def get_merge_request(self, iid: int):
        """Get a specific Merge Request."""
        try:
            return self.project.mergerequests.get(iid)
        except Exception:
            return None

    def get_file_content(self, file_path: str, ref: str = "main"):
        """Get content of a file from the repository."""
        try:
            f = self.project.files.get(file_path=file_path, ref=ref)
            return f.decode().decode("utf-8")
        except Exception:
            return None

    def file_exists(self, file_path: str, ref: str = "main") -> bool:
        """Check if a file exists in the repository."""
        try:
            self.project.files.get(file_path=file_path, ref=ref)
            return True
        except Exception:
            return False

    def create_branch(self, branch_name: str, ref: str = "main"):
        """Create a new branch in GitLab."""
        try:
            self.project.branches.create({"branch": branch_name, "ref": ref})
            logger.info(f"Created branch {branch_name} from {ref}")
            return True
        except Exception as e:
            logger.error(f"Error creating branch {branch_name}: {e}")
            return False

    def commit_changes(self, branch_name: str, commit_message: str, actions: list):
        """
        Create a commit with multiple file actions.
        'actions' is a list of dicts: {'action': 'create'|'update', 'file_path': '...', 'content': '...'}
        """
        data = {
            "branch": branch_name,
            "commit_message": commit_message,
            "actions": actions
        }
        try:
            self.project.commits.create(data)
            logger.info(f"Committed changes to branch {branch_name}")
            return True
        except Exception as e:
            logger.error(f"Error committing changes to {branch_name}: {e}")
            return False
