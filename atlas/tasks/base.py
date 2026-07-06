from abc import ABC, abstractmethod

from atlas.models.tasks import Task, TaskList


class TasksAdapter(ABC):
    @abstractmethod
    def list_task_lists(self) -> list[TaskList]:
        raise NotImplementedError

    @abstractmethod
    def list_tasks(self, list_id: str) -> list[Task]:
        raise NotImplementedError

    @abstractmethod
    def complete_task(self, list_id: str, task_id: str) -> None:
        raise NotImplementedError
