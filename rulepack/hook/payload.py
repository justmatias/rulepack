from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def parse_patch_paths(patch: str) -> list[str]:
    """The files an apply_patch command adds or updates, after any move."""
    paths: list[str] = []
    updating = False
    for line in patch.split("\n"):
        # Leading whitespace in an update hunk marks unchanged file content.
        header, _, path = (line.rstrip() if updating else line.strip()).partition(": ")
        if not path:
            continue
        match header:
            case "*** Update File":
                paths.append(path)
                updating = True
            case "*** Add File":
                paths.append(path)
                updating = False
            case "*** Delete File":
                updating = False
            case "*** Move to" if updating:
                paths[-1] = path
    return paths


class ToolInput(BaseModel):
    file_path: str | None = None
    command: str | None = None


class HookPayload(BaseModel):
    """The fields rulepack reads from an agent's hook payload; others are ignored."""

    model_config = ConfigDict(coerce_numbers_to_str=True)

    cwd: str | None = None
    workspace_roots: list[str] = Field(default_factory=list)
    file_path: str | None = None
    tool_name: str | None = None
    tool_input: ToolInput | None = None
    session_id: str = ""

    def resolve_directory(self) -> Path:
        """The agent's cwd, else the workspace root that holds the edited file."""
        if self.cwd:
            return Path(self.cwd).resolve()
        if self.file_path is not None:
            edited = Path(self.file_path).resolve()
            for workspace in self.workspace_roots:
                if edited.is_relative_to(root := Path(workspace).resolve()):
                    return root
        return Path.cwd()

    def list_edited_paths(self, directory: Path) -> list[Path]:
        if self.tool_name == "apply_patch" and self.tool_input is not None:
            patch = self.tool_input.command or ""
            return [(directory / path).resolve() for path in parse_patch_paths(patch)]
        path = self.tool_input.file_path if self.tool_input else self.file_path
        return [(directory / path).resolve()] if path else []
