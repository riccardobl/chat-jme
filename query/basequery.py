from abc import ABC, abstractmethod
class BaseQuery(ABC):
    @abstractmethod
    def getAffineDocs(self, question, context, keywords, wordSalad=None, unitFilter=None):
        pass
