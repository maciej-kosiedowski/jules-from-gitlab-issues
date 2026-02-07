import sys

with open('src/core/jules_client.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'def get_source_name(self) -> Optional[str]:' in line:
        new_lines.append(line)
        new_lines.append('        """Find the source name for the configured GitHub repo."""\n')
        new_lines.append('        if self._cached_source_name:\n')
        new_lines.append('            return self._cached_source_name\n')
        new_lines.append('\n')
        new_lines.append('        try:\n')
        new_lines.append('            sources = self._get("sources").get("sources", [])\n')
        new_lines.append('            owner_repo = settings.GITHUB_REPO.lower()\n')
        new_lines.append('            for source in sources:\n')
        new_lines.append('                if source.get("id", "").lower() == f"github/{owner_repo}":\n')
        new_lines.append('                    self._cached_source_name = source.get("name")\n')
        new_lines.append('                    return self._cached_source_name\n')
        new_lines.append('        except Exception as e:\n')
        new_lines.append('            logger.error(f"Error fetching sources: {e}")\n')
        # Here's the change: return the fallback without caching it
        new_lines.append('        return f"sources/github/{settings.GITHUB_REPO}"\n')
        skip = True
    elif skip:
        if 'def create_session' in line:
            skip = False
            new_lines.append('\n')
            new_lines.append(line)
        else:
            continue
    else:
        new_lines.append(line)

with open('src/core/jules_client.py', 'w') as f:
    f.writelines(new_lines)
