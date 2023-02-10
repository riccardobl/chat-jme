
import os,json
from embeddings import EmbeddingsManager
from . import basequery
import utils

class EmbeddingsQuery(basequery.BaseQuery):
    def __init__(self, config):
        EmbeddingsQuery.CONFIG = config
 
    def _getIndices(self,wordSalad, unitFilter=None):
        CONFIG=EmbeddingsQuery.CONFIG
        loaded_parts = []
        for unit in os.listdir(CONFIG["INDEX_PATH"]):
            if unitFilter!=None and not unitFilter(unit):
                continue

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
                        print("Found",w,"in",wordSalad)
                        break
            if included:
                print("Include",unit)
                path=os.path.join(CONFIG["INDEX_PATH"],unit)
                parts=[os.path.join(path, file) for file in os.listdir(path)]
                for part in parts:
                    if not part.endswith(".bin") and not part.endswith(".binZ"): continue
                    try:
                        loaded_parts.append(EmbeddingsManager.read(part))
                    except Exception as e:
                        print("Error loading", part, e)
                        continue    
        return  loaded_parts
    

    def getAffineDocs(self, question, context, keywords, shortQuestion,  wordSalad=None, unitFilter=None,
        maxFragmentsToReturn=3, maxFragmentsToSelect=12, merge=False):
        indices = self._getIndices(wordSalad, unitFilter)
        return   EmbeddingsManager.query(
            indices,[question,context],group=EmbeddingsManager.GROUP_GPU_CACHE,
            k=maxFragmentsToSelect,n=maxFragmentsToReturn    
        )
                