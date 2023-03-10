from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from ratelimit import limits,sleep_and_retry
import pickle
from langchain.docstore.document import Document
import numpy as np
import time
from langchain.text_splitter import CharacterTextSplitter
import utils
import gc
from OpenAICachedEmbeddings import OpenAICachedEmbeddings
import faiss
import hashlib
from threading import Lock
import copy,gzip
import bz2
import os
from TorchEmbeddings import TorchEmbeddings
# Group 0 = cache and gpu
# Group 1 = not cache, gpu
# Group -1 = not cache, not gpu
# Group 2 = cache, not gpu
class EmbeddingsManager:
    CONFIG=None
    LOAD_CACHE=None
    GPU_CACHE=None
    GPU_RESOURCES=None
    GROUP_GPU_CACHE=0
    GROUP_GPU=1
    GROUP_CPU=-1
    GROUP_CPU_CACHE=2

    @staticmethod
    def _withCache(group):
        if not EmbeddingsManager.CONFIG.get("CACHE_EMBEDDINGS",True):
            return False            
        return group==EmbeddingsManager.GROUP_GPU_CACHE or group==EmbeddingsManager.GROUP_CPU_CACHE

    @staticmethod
    def _withGpu(group):
        return group==EmbeddingsManager.GROUP_GPU or group==EmbeddingsManager.GROUP_GPU_CACHE

    @staticmethod
    def init(CONFIG):
        EmbeddingsManager.CONFIG=CONFIG
        EmbeddingsManager.LOAD_CACHE={}
        EmbeddingsManager.GPU_CACHE={}
        EmbeddingsManager.GPU_RESOURCES=None
        useGpu=EmbeddingsManager.CONFIG["DEVICE"]=="cuda" or EmbeddingsManager.CONFIG["DEVICE"]=="gpu"
        if useGpu:
            EmbeddingsManager.GPU_RESOURCES=faiss.StandardGpuResources()
        device=CONFIG.get("DEVICE","cpu")
        TorchEmbeddings.init(device)
   

    @staticmethod
    def _toDevice(f,group=0):
        if EmbeddingsManager.GPU_RESOURCES==None or not EmbeddingsManager._withGpu(group):
            return [f,lambda: None]
        else:
            if not group in EmbeddingsManager.GPU_CACHE:
                EmbeddingsManager.GPU_CACHE[group]={}
            cache=EmbeddingsManager.GPU_CACHE[group]
            if hash(f) in cache:
                return [cache[hash(f)],lambda: None]
            else:
                gpuIndex=copy.copy(f)
                internalIndex=gpuIndex.index
                internalIndexToGpu=faiss.index_cpu_to_gpu(EmbeddingsManager.GPU_RESOURCES,0,internalIndex)
                gpuIndex.index=internalIndexToGpu
                if EmbeddingsManager._withCache(group):
                    cache[hash(f)]=gpuIndex
                    return [gpuIndex,lambda: None]
                else:
                    def release():
                        nonlocal gpuIndex
                        internalIndexToGpu.reset()
                        del gpuIndex
                    return [gpuIndex,release]
               



 
        
   
    @staticmethod
    def new(docs,backend="openai"):
        
           
        if not isinstance(docs, list):
            docs=[docs]
        
        docs=copy.copy(docs)
        for i in range(len(docs)):
            if isinstance(docs[i], str):
                metadata={"source": "", "hash": ""}
                docs[i]=Document(page_content=docs[i], metadata=metadata)
        

        if backend=="openai":
            return EmbeddingsManager._newOpenAI(docs)
        else: 
            return EmbeddingsManager._newTorch(docs,backend)

    @staticmethod
    def _newTorch(docs,backend):
        source_chunks = []
        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1500,
            chunk_overlap=1000,
            length_function=len,
        )
        for doc in docs:
            for chunk in splitter.split_text(doc.page_content):
                source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))          
        try:
            faiss=FAISS.from_documents(source_chunks, TorchEmbeddings())     
            return faiss                 
        except Exception as e:
            print(e)


    @staticmethod
    def _newOpenAI(docs):        
        source_chunks = []

        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        for doc in docs:
            for chunk in splitter.split_text(doc.page_content):
                source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
        
        try:
            l=40
            source_chunks = [source_chunks[i:i + l] for i in range(0, len(source_chunks), l)]
            print("Processing", len(source_chunks),"chunks")               
            print("Create index with",len(source_chunks[0]),"tokens")
            faiss=utils.retry(lambda: FAISS.from_documents(source_chunks[0], OpenAIEmbeddings()))
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
            index.embedding_function=OpenAICachedEmbeddings(cachePath=os.path.join(EmbeddingsManager.CONFIG["CACHE_PATH"],"openaiembeddings")).embed_query
        return utils.retry(lambda:index.embedding_function(query))

    
    @staticmethod
    def embedding_function2(index, queries):
        t=TorchEmbeddings()
        return t._embedding_func2(queries)
  
    @staticmethod
    def write(path,embed):
        compressed=path.endswith("Z")
        if embed==None:
            raise Exception("Can't write None")
        if not compressed:       
            with open(path, 'wb') as f:      
                pickle.dump(embed, f, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            with bz2.BZ2File(path,"wb") as f: 
                pickle.dump(embed, f, protocol=pickle.HIGHEST_PROTOCOL)


    @staticmethod
    def read(path, group=0):
        if path in EmbeddingsManager.LOAD_CACHE:
            return EmbeddingsManager.LOAD_CACHE[path]
        compressed=path.endswith("Z")
        
        f=open(path, 'rb') if not compressed else bz2.BZ2File(path, "rb")
        print("Loading from disk",path,"...")
        out = pickle.load(f)
        f.close()

        if EmbeddingsManager._withCache(group):
            EmbeddingsManager.LOAD_CACHE[path]=out
        if out==None:
            raise Exception("Error loading index")
        
        return out
        


    @staticmethod
    def queryIndex(index,query,k=4, cache=None, group=0):
        embedding=None

        if isinstance(query, str):
            if cache!=None and query in cache:
                embedding=cache[query]
            else:
                embedding =  EmbeddingsManager.embedding_function(index, query)
                if cache!=None:
                    cache[query]=embedding
        else:
            embedding=query
        
        [index,release]=EmbeddingsManager._toDevice(index,group)
        scores, indices = index.index.search(np.array([embedding], dtype=np.float32), k=k)
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
        if release is not None: release()
        return docs


    def query(indices, query, n=6, k=12,cache=None,group=0):
        results=[]
        print("Searching",len(indices),"embeddings...")
        # if query is array
        if not isinstance(query, list):
            query=[query]
        if len(indices)>0:
            for q in query:            
                print("Compute embedding for query",query)
                embeddings={}
                for index in indices:
                    generator=index.embedding_function.__qualname__.split(".")[0]
                    embedding=None
                    if generator not in embeddings:
                        embeddings[generator]= embedding= EmbeddingsManager.embedding_function(index, q)
                    else:
                        embedding=embeddings[generator]
                    res=EmbeddingsManager.queryIndex(index,embedding, k=k, cache=None,group=group),
                    for res2 in res:
                        for rdoc in res2:
                            score=rdoc[1]
                            found=False
                            for r in results:
                                if r["doc"]==rdoc[0]:                        
                                    found=True
                                    break
                            if not found:
                                results.append({
                                    "doc": rdoc[0],
                                    "score": score
                                })       


        

        best= sorted(results, key=lambda x: x["score"], reverse=False)[:n]
    
        return [ x["doc"] for x in best]
