from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from ratelimit import limits,sleep_and_retry
import pickle
from langchain.docstore.document import Document
import numpy as np
class Embeddings:
    cache={}

    @sleep_and_retry
    @limits(calls=40, period=70)
    @staticmethod
    def _rateLimit(chunk):
        return chunk
        
    @staticmethod
    def new(source_chunks):
        for chunk in source_chunks:
            Embeddings._rateLimit(chunk)            
        return FAISS.from_documents(source_chunks, OpenAIEmbeddings())

    @staticmethod
    def write(path,embed):
        with open(path, 'wb') as f:
            pickle.dump(embed, f)

    @staticmethod
    def read(path):
        with open(path, 'rb') as f:
            return pickle.load(f)

    @staticmethod
    def cachedQuery(index,query,k=4):
        embedding=None
        if query in Embeddings.cache :
            embedding=Embeddings.cache[query]
        else:
            embedding=index.embedding_function(query)
            Embeddings.cache[query]=embedding

        scores, indices = index.index.search(np.array([embedding], dtype=np.float32), k)
        docs = []
        for j, i in enumerate(indices[0]):
            if i == -1:
                # This happens when not enough docs are returned.
                continue
            _id = index.index_to_docstore_id[i]
            doc = index.docstore.search(_id)
            if not isinstance(doc, Document):
                raise ValueError(f"Could not find document for id {_id}, got {doc}")
            docs.append((doc, scores[0][j]))
        return docs

    def query(indices, query, n=3, k=4):
        results=[]
        for index in indices:
            print("Search",index)
            res=Embeddings.cachedQuery(index,query, k=k),
            for res2 in res:
                for rdoc in res2:
                    results.append({
                        "doc": rdoc[0],
                        "score": rdoc[1]
                    })        
        best= sorted(results, key=lambda x: x["score"], reverse=False)[:n]
        #best[::-1]      
        return [ x["doc"] for x in best]
