
import os,json
from embeddings import EmbeddingsManager
from . import basequery

class EmbeddingsQuery(basequery.BaseQuery):
    def __init__(self, config):
        EmbeddingsQuery.CONFIG = config

    def _getIndices(self,wordSalad, unitFilter=None):
        CONFIG=EmbeddingsQuery.CONFIG
        loaded_parts = []
        # for each folder in CONFIG["INDEX_PATH"]
        for unit in os.listdir(CONFIG["INDEX_PATH"]):
            if unitFilter!=None and not unitFilter(unit):
                continue

            #load info.json
            infoPath = os.path.join(CONFIG["INDEX_PATH"],unit,"info.json")
            info={}
            if os.path.exists(infoPath):
                with open(infoPath,"r",encoding="utf-8") as f:
                    info = json.loads(f.read())
            included=wordSalad==None or len(info["triggerWords"])==0
            if not included:
                for w in info["triggerWords"]:
                    if w.lower() in wordSalad.lower():
                        included=True
                        break
            if included:
                path=os.path.join(CONFIG["INDEX_PATH"],unit)
                parts=[os.path.join(path, file) for file in os.listdir(path)]
                for part in parts:
                    if not part.endswith(".bin"): continue
                    try:
                        loaded_parts.append(EmbeddingsManager.read(part))
                    except Exception as e:
                        print("Error loading", part, e)
                        continue    
        return  loaded_parts
    

    def getAffineDocs(self, question, wordSalad=None, unitFilter=None):
        indices = self._getIndices(wordSalad, unitFilter)
        return EmbeddingsManager.query(indices,question)        