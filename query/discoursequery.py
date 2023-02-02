
import os,json
import hashlib
from langchain.docstore.document import Document
import requests
import markdownify
from langchain import OpenAI, PromptTemplate, LLMChain
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains.mapreduce import MapReduceChain
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from sumy.parsers.html import HtmlParser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
from bs4 import BeautifulSoup
from embeddings import EmbeddingsManager
from . import basequery


    

class DiscourseQuery( basequery.BaseQuery):
    def __init__(self, config,url, apiKey=None, apiSecret=None):
        self.CONFIG = config
        self.url = url
        # self.llm = OpenAI(temperature=0)
        # self.text_splitter = CharacterTextSplitter()
        # self.summaryChain= load_summarize_chain(self.llm, chain_type="stuff")



    def _createDoc(self,content,link):
        content = "\n".join([t for t in content.split("\n") if t])
        hash=hashlib.sha256(link.encode('utf-8')).hexdigest()    
        doc = Document(page_content=content, metadata={"source": link, "hash":hash})
        return doc

    def _summarize(self,content,url,sentences_count=4, withCodeBlocks=True):
        LANGUAGE="english"
        SENTENCES_COUNT = sentences_count
        stemmer = Stemmer(LANGUAGE)
        summarizer = Summarizer(stemmer)
        summarizer.stop_words = get_stop_words(LANGUAGE)
        parser = HtmlParser.from_string(content, url=url,tokenizer=Tokenizer(LANGUAGE))
        text_summary=""
        for sentence in summarizer(parser.document, SENTENCES_COUNT):
            text_summary+=str(sentence)

        if withCodeBlocks:
            # extract code blocks and add them back to the summary
            soup = BeautifulSoup(content, 'html.parser')
            codeBlocks=soup.find_all("pre")
            for codeBlock in codeBlocks:
                text_summary+="<pre><code>"
                text_summary+=codeBlock.text
                text_summary+="</code></pre>"

        return text_summary

    def _parseTopic(self,topicId):
        discourseUrl=self.url
        url = f"{discourseUrl}/t/{topicId}.json"

        d=None
        def getData():
            nonlocal d
            if d!=None: return d
            print("Fetch",url)
            headers = {    }
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise Exception("Error fetching topic "+topicId)
            d=response.json()
            return d

        v=self._loadFromCache(topicId,True)
        if not v:
            print("Get initial question of",topicId)
            data=getData()
            initialQuestion=data["title"]+"\n"+data["post_stream"]["posts"][0]["cooked"]
            v=EmbeddingsManager.new(Document(page_content=initialQuestion),"cpu")
            self._saveToCache(topicId,v,True)
        else:
            print("Get initial question from cache",topicId)

        def getContent():
            content=self._loadFromCache(topicId,False)
            if content==None: 
                data=getData()
                print("Process",topicId)
                content=""
                contentPart=""
                isQuestion=True
                isFirst=True
                topicAuthorId=data["user_id"]
                posts = data["post_stream"]["posts"]
                def flush():
                    nonlocal contentPart
                    nonlocal content
                    nonlocal isQuestion
                    nonlocal isFirst
                    if len(contentPart)==0: return
                    contentPart=self._summarize(contentPart,f"{discourseUrl}/t/{topicId}",sentences_count=1 if isQuestion else 3,withCodeBlocks=not isQuestion)
                    if isQuestion:
                        content+="\n\nQUESTION:\n"
                        if isFirst:
                            content+=data["title"]+"\n"  
                            isFirst=False
                    else:
                        content+="\n\nANSWER:\n"                
                    content+=contentPart
                    contentPart=""                        
                for post in posts:
                    postAuthorId=post["user_id"]
                    postText=post["cooked"]                
                    if isQuestion and postAuthorId!=topicAuthorId:
                        flush()
                        isQuestion=False
                    elif not isQuestion and postAuthorId==topicAuthorId:
                        flush()
                        isQuestion=True     
                    contentPart+=postText+"\n"
                flush()
                content = markdownify.markdownify(content, heading_style="ATX",autolinks=True,escape_asterisks=False,escape_underscores=False)
                self._saveToCache(topicId,content,False)
            else:  
                print("Get from cache",topicId)
            return self._createDoc( content,discourseUrl+"/t/"+str(topicId))
        # texts = self.text_splitter.split_text(content)
        # docs = [Document(page_content=t) for t in texts]
        # content=self.summaryChain.run(docs)
        # print(content)

        #print("Create embeddings for",initialQuestion)

        #print(v)
        # create VectorStore
        # initialQuestion
        return {
            "id":topicId,
            "content":getContent,
            "v":v
        }

    def _getCachePath(self,id):
        urlHash=hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        cacheRoot=os.path.join(self.CONFIG["CACHE_PATH"],"discourse",urlHash)
        cachePath=os.path.join(cacheRoot,str(id))
        if not os.path.exists(cachePath):
            os.makedirs(cachePath)
        return cachePath

    def _loadFromCache(self,id, isEmbedding):
        try:
            cachePath=self._getCachePath(id)
            if isEmbedding :
                f=os.path.join(cachePath,"question.bin")
                if os.path.exists(f):
                    v=EmbeddingsManager.read(f)
                    return v 
            else:
                f=os.path.join(cachePath,"content.txt")
                if os.path.exists(f):
                    with open(f, 'r') as f:
                        content = f.read()
                        return content     
        except Exception as e:
            print("Error loading from cache",e)
        return None
    
    def _saveToCache(self,id,v, isEmbedding):
        try:
            cachePath=self._getCachePath(id)
            if isEmbedding :
                f=os.path.join(cachePath,"question.bin")
                EmbeddingsManager.write(f,v)
            else:
                f=os.path.join(cachePath,"content.txt")
                with open(f, 'w') as f:
                    f.write(v)
        except Exception as e:
            print("Error saving to cache",isEmbedding,e)
 
    def _search(self,question,limit=10,n=1):

        discourseUrl=self.url

        params = {
            "q": question+" in:first order:likes"
        }        
        response = requests.get(discourseUrl+"/search.json", params=params)
        if response.status_code != 200:
            raise Exception("Error searching discourse")

        jsonData=response.json()
        
        topics=[]
        if not "topics" in jsonData: return [];
        for topic in jsonData["topics"]:
            if len(topics)>=limit: break
            id=topic["id"]
            topicData=self._parseTopic(id)
            topics.append(topicData)

        for topic in topics:
            res=EmbeddingsManager.queryIndex(topic["v"],question, k=1)
            score=None
            for rdoc in res:
                rscore=rdoc[1]
                if not score or rscore<score:
                    score=rscore
            topic["score"]=score
        
        topics = sorted(topics, key=lambda x: x["score"], reverse=False)[:n]
        topics = [ x["content"]() for x in topics]
        return topics

    def getAffineDocs(self, question, wordSalad=None, unitFilter=None):
        return self._search(question, 4)        

