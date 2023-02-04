
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
import gc
import urllib
import utils
from Summary import Summary

# This contains several Ugly hacks to contain memory usage.
# Needs a rewrite!
class DiscourseQuery( basequery.BaseQuery):
    def __init__(self, config,url, searchFilter="in:first order:likes", knowledgeCutoff="2023-02-03",apiKey=None, apiSecret=None):
        self.CONFIG = config
        self.url = url
        self.searchFilter=searchFilter
        self.knowledgeCutoff=knowledgeCutoff


    def _createFragments(self,topicId,content,link):
        content = "\n".join([t for t in content.split("\n") if t])
        hash=hashlib.sha256(link.encode('utf-8')).hexdigest()    
        doc = Document(page_content=content, metadata={"source": link, "hash":hash})

        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1024,
            chunk_overlap=0,
            length_function=len,
        )
        frags=[]
        i=0
        for chunk in splitter.split_text(doc.page_content):
            doc=Document(page_content=chunk, metadata=doc.metadata)
            fragmentId=str(topicId)+"-"+str(i)
            v=self._loadFromCache(fragmentId,True)
            if v==None:
                if not v:
                    v=EmbeddingsManager.new(doc,self.CONFIG["DEVICE"])
                    self._saveToCache(fragmentId,v,True)
            frags.append(v)
        return frags

    # def _summarize(self,content,url,sentences_count=4, withCodeBlocks=True):
    #     try:
    #         LANGUAGE="english"
    #         SENTENCES_COUNT = sentences_count
    #         stemmer = Stemmer(LANGUAGE)
    #         summarizer = Summarizer(stemmer)
    #         summarizer.stop_words = get_stop_words(LANGUAGE)
    #         parser = HtmlParser.from_string(content, url=url,tokenizer=Tokenizer(LANGUAGE))
    #         text_summary=""
    #         for sentence in summarizer(parser.document, SENTENCES_COUNT):
    #             text_summary+=str(sentence)

    #         if withCodeBlocks:
    #             # extract code blocks and add them back to the summary
    #             soup = BeautifulSoup(content, 'html.parser')
    #             codeBlocks=soup.find_all("pre")
    #             for codeBlock in codeBlocks:
    #                 text_summary+="<pre><code>"
    #                 text_summary+=codeBlock.text
    #                 text_summary+="</code></pre>"
    #         gc.collect()
    #         return text_summary
    #     except Exception as e:
    #         print("Error summarizing",e)
    #         return ""

    def _parseTopic(self,topicId, maxNumReplies=5):
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

        def getV():
            v=self._loadFromCache(topicId,True)
            if not v:
                print("Get initial question of",topicId)
                data=getData()
                initialQuestion=data["title"]+"\n"+data["post_stream"]["posts"][0]["cooked"]
                v=EmbeddingsManager.new(Document(page_content=initialQuestion),self.CONFIG["DEVICE"])
                self._saveToCache(topicId,v,True)
            else:
                print("Get initial question from cache",topicId)
            return v

        def getContent():
            content=self._loadFromCache(topicId,False)
            if content==None: 
                data=getData()
                print("Process",topicId)
                content=[]
                contentPart=""
                isQuestion=True
                isFirst=True
                topicAuthorId=data["user_id"]
                posts = data["post_stream"]["posts"]
                def flush():
                    nonlocal contentPart
                    nonlocal isQuestion
                    nonlocal isFirst
                    if len(contentPart)==0: return
                    minLen=100
                    maxLen=300
                    if isQuestion:
                        minLen=100
                        maxLen=500
                    contentPart=Summary.summarizeHTML(contentPart,f"{discourseUrl}/t/{topicId}",max_length=maxLen,min_length=minLen,withCodeBlocks=not isQuestion)
                    c=""
                    if isQuestion:
                        c+="\n\nQUESTION:\n"
                        if isFirst:
                            author=data["post_stream"]["posts"][0]["name"]
                            if author==None: author=data["post_stream"]["posts"][0]["username"]
                            c+=data["title"]+"\n"+"Author: "+author+"\n"  
                            isFirst=False
                    else:
                        c+="\n\nANSWER:\n"                
                    c+=contentPart
                    contentPart=""    
                    content.append(c)                    
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

                if len(content)>maxNumReplies:
                    content=content[:1]+content[-maxNumReplies:]
                content="\n".join(content)

                content = markdownify.markdownify(content, heading_style="ATX",autolinks=True,escape_asterisks=False,escape_underscores=False)
                self._saveToCache(topicId,content,False)
            else:  
                print("Get from cache",topicId)
            return self._createFragments(topicId, content,discourseUrl+"/t/"+str(topicId))
        return {
            "id":topicId,
            "frags":getContent,
            "v":getV
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
                    v=EmbeddingsManager.read(f,group=-1)
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
 
    def _search(self, searchTerms, question,searchLimit=1,maxTopicsToSelect=3,maxFragmentsToSelect=3,maxNumReplies=5, merge=True):
        discourseUrl=self.url


        # Search
        topics=[]
        for term in searchTerms:
            termTopics=[]
            def search():    
                params = {
                    "q": term+" "+self.searchFilter+" before:"+self.knowledgeCutoff
                }        
                print("searching",discourseUrl, params)
                response = requests.get(discourseUrl+"/search.json", params=params)
                if response.status_code != 200:
                    print("Error searching discourse")
                    raise Exception("Error searching discourse")
                jsonData=response.json()        
                return jsonData

            try:
                jsonData= utils.retry(search,3,1)
                if not "topics" in jsonData: return []
                for topic in jsonData["topics"]:
                    if len(termTopics)>=searchLimit: break
                    id=topic["id"]
                    topicData=self._parseTopic(id,maxNumReplies)
                    termTopics.append(topicData)
                topics.extend(termTopics)
            except Exception as e:
                print("Error searching discourse",e)

        cache={}
        for topic in topics:
            v=topic["v"]
            res=EmbeddingsManager.queryIndex(v(),question, k=1, cache=cache, group=EmbeddingsManager.GROUP_GPU)
            score=None
            for rdoc in res:
                rscore=rdoc[1]
                if not score or rscore<score:
                    score=rscore
            topic["score"]=score
            gc.collect()       
                
        topics = sorted(topics, key=lambda x: x["score"], reverse=False)[:maxTopicsToSelect]
        gc.collect()

        fragments=[]
        for t in topics:
            fragments.extend(t["frags"]())            
        topics=EmbeddingsManager.query(fragments,question, k=maxFragmentsToSelect, cache=cache, group=EmbeddingsManager.GROUP_GPU)           
        if merge:
            print("Found",len(topics),"topics, Merge")        
            mergedTopic=""
            for t in topics:
                mergedTopic+=t.page_content+"\n"
            mergedTopic=Summary.summarizeHTML(mergedTopic,min_length=200,max_length=512,withCodeBlocks=True)
            print("Merged in ",len(mergedTopic),"chars")
            topics= [Document(page_content=mergedTopic, metadata={"source": f"{discourseUrl}/search", "hash":""})]
        return topics

    def getAffineDocs(self, question, shortQuestion, context, keywords,  wordSalad=None, unitFilter=None):
        seachTerms=[]
        #seachTerms.append(question)
        seachTerms.extend(keywords)
        seachTerms=seachTerms[:3]
        return self._search(seachTerms,question)        

