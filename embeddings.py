from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from ratelimit import limits,sleep_and_retry
import pickle
from langchain.docstore.document import Document
import numpy as np
import time
from langchain.text_splitter import CharacterTextSplitter
from TorchEmbeddings import TorchEmbeddings
import utils
import gc
from OpenAICachedEmbeddings import OpenAICachedEmbeddings
class EmbeddingsManager:

   
    @staticmethod
    def new(doc,backend="openai"):
        if backend=="cpu" or backend=="gpu":
            return EmbeddingsManager._newTorch(doc,backend)
        else: # backend==openai
            return EmbeddingsManager._newOpenAI(doc)

    @staticmethod
    def _newTorch(doc,backend):
        source_chunks = []
        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        for chunk in splitter.split_text(doc.page_content):
            source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))          
        try:
            l=40
            source_chunks = [source_chunks[i:i + l] for i in range(0, len(source_chunks), l)]
            print("Processing", len(source_chunks),"chunks")               
            print("Create index with",len(source_chunks[0]),"tokens")
            faiss=FAISS.from_documents(source_chunks[0], TorchEmbeddings(backend))
            if faiss==None:
                raise Exception("Error creating index")
            if len(source_chunks)>1:
                for i in range(1,len(source_chunks)):
                    documents=source_chunks[i]
                    print("Add",len(documents),"tokens")
                    texts = [d.page_content for d in documents]
                    metadatas = [d.metadata for d in documents]
                    faiss.add_texts(texts,metadatas)       
            return faiss                 
        except Exception as e:
            print(e)


    @staticmethod
    def _newOpenAI(doc):
        source_chunks = []

        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        for chunk in splitter.split_text(doc.page_content):
            source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
        
        try:
            l=40
            source_chunks = [source_chunks[i:i + l] for i in range(0, len(source_chunks), l)]
            print("Processing", len(source_chunks),"chunks")               
            print("Create index with",len(source_chunks[0]),"tokens")
            faiss=utils.retry(lambda: FAISS.from_documents(source_chunks[0], OpenAICachedEmbeddings()))
            if faiss==None:
                raise Exception("Error creating index")
            if len(source_chunks)>1:
                for i in range(1,len(source_chunks)):
                    documents=source_chunks[i]
                    print("Add",len(documents),"tokens")
                    texts = [d.page_content for d in documents]
                    metadatas = [d.metadata for d in documents]
                    utils.retry(lambda: faiss.add_texts(texts,metadatas))       
            return faiss                 
        except Exception as e:
            print("Error creating index. Retry ", e)

     
 

    @staticmethod
    def embedding_function(index, query):
        if index.embedding_function.__qualname__.startswith("OpenAIEmbeddings."): # Migrate to cached embeddings
            index.embedding_function=OpenAICachedEmbeddings().embed_query
        return utils.retry(lambda:index.embedding_function(query))
  
    @staticmethod
    def write(path,embed):
        if embed==None:
            raise Exception("Can't write None")
        with open(path, 'wb') as f:      
            pickle.dump(embed, f)

    @staticmethod
    def read(path):
        with open(path, 'rb') as f:
            out = pickle.load(f)
            if out==None:
                raise Exception("Error loading index")
            return out

    @staticmethod
    def queryIndex(index,query,k=4, cache=None):
        embedding=None
        if cache!=None and query in cache:
            embedding=cache[query]
        else:
            embedding =  EmbeddingsManager.embedding_function(index, query)
            if cache!=None:
                cache[query]=embedding
        # embedding=None

        # print(index.embedding_function.__class__.__name__)
        # backend=hash(index.embedding_function)
        
        # if not backend in EmbeddingsManager.cache:
        #     EmbeddingsManager.cache[backend]={}
        
        # cache=EmbeddingsManager.cache[backend]
        # # prevent cache from growing too big
        # if len(cache)>1000:
        #     cache={}

        # if query in cache :
        #     print("Cached")
        #     embedding=cache[query]
        # else:
        #     #embedding=index.embedding_function(query)
        #     embedding=EmbeddingsManager.embedding_function(index, query)
        #     cache[query]=embedding
        
       
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

    def query(indices, query, n=3, k=4,cache=None):
        results=[]
        if cache==None: 
            cache={}
        for index in indices:
            print("Search",index)
            res=EmbeddingsManager.queryIndex(index,query, k=k, cache=cache),
            for res2 in res:
                for rdoc in res2:
                    results.append({
                        "doc": rdoc[0],
                        "score": rdoc[1]
                    })        
        best= sorted(results, key=lambda x: x["score"], reverse=False)[:n]
        #best[::-1]      
        gc.collect()
        gc.collect()
        return [ x["doc"] for x in best]
