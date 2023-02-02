from abc import ABC, abstractmethod
class BaseQuery(ABC):
    @abstractmethod
    def getAffineDocs(self, question, wordSalad=None, unitFilter=None):
        pass
