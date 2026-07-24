from abc import ABC, abstractmethod


class Seedable(ABC):
    @abstractmethod
    def seed(self):
        pass