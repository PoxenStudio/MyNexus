from dataclasses import dataclass


@dataclass
class TaskProgress:
    task_id: str
    progress: int
    stage: str
    message: str = ""
