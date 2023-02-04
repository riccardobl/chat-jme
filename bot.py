import os
import traceback
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
import langchain
from langchain.cache import InMemoryCache
from langchain.llms import OpenAI
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory,ConversationBufferMemory,ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from embeddings import EmbeddingsManager
from flask import Flask, send_from_directory
import json
import time
import threading
import secrets
import string
import hashlib
from flask import request
from langchain.cache import InMemoryCache,SQLiteCache
import re
import requests
from waitress import serve
from translator import Translator
import sys
from query.discoursequery import DiscourseQuery
from query.embeddingsquery import EmbeddingsQuery
from Summary import Summary
import uuid
CONFIG=None
QUERIERS=[]

args=sys.argv
confiFile=args[1] if len(args)>1 else "config.json"
print("Use config file", confiFile)
with open(confiFile, "r") as f:
    CONFIG=json.load(f)
    EmbeddingsManager.init(CONFIG)
    Summary.init(CONFIG)
    QUERIERS=[
        EmbeddingsQuery(CONFIG),
        DiscourseQuery(
            CONFIG,CONFIG["JME_HUB_URL"],
            searchFilter=CONFIG["JME_HUB_SEARCH_FILTER"],
            knowledgeCutoff=CONFIG["JME_HUB_KNOWLEDGE_CUTOFF"]
        )
    ]
    Translator.init(CONFIG)

def getAffineDocs(question,context,keywords,shortQuestion, wordSalad=None, unitFilter=None):
    affineDocs=[]

   
    for q in QUERIERS:
        print("Get affine docs from",q,"using question",question,"with context",context,"and keywords",keywords)
        t=time.time()
        v=q.getAffineDocs(question, context, keywords,shortQuestion, wordSalad, unitFilter)
        print("Completed in",time.time()-t,"seconds.")
        if v!=None:
            affineDocs.extend(v)
    return affineDocs
    
def rewriteError(error):
    if error.startswith("Rate limit reached ") :
        return "Rate limit."

def rewrite(question):
    # replace app, applet, game, application with simple application 
    question=re.sub(r"\b(app|applet|game|application)\b", "simple application", question, flags=re.IGNORECASE)

    return question


def createChain():
    template = """You are an AI assistant for the open source game engine jMonkeyEngine. 
The documentation is located at https://wiki.jmonkeyengine.org . 
The source code is located at this github repository https://github.com/jMonkeyEngine/jmonkeyengine/ .
In the answer includes a code snippet as an example.
When replying consider these rules:
- Applets are not supported anymore so don't answer things related to Applets.
- When the question contains "show me the code", write a code snippet in the answer.
- IOs is not supported anymore so don't answer things related to IOs.
- You can use any code from github and the documentation

Given the following extracted parts of a long document and a question, create a conversational final answer with references ("SOURCES"). 
ALWAYS prefix "SOURCES" with four new lines.

========= 
{summaries}
=========
{history}

QUESTION: {question}
FINAL ANSWER in Markdown: """



    prompt = PromptTemplate(
        input_variables=[ "history", "question", "summaries"], 
        template=template
    )


    memory=ConversationSummaryBufferMemory(llm=OpenAI(), max_token_limit=600,human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    chain = load_qa_with_sources_chain(
        OpenAI(
            temperature=0.0,
            model_name="text-davinci-003",
            max_tokens=2048,
        ), 
        memory=memory, 
        prompt=prompt, 
        verbose=True,
    )
    return chain

def queryCache(wordSalad,shortQuestion,cacheConf):    
    levels=[None]*len(cacheConf)
    for i in range(len(cacheConf)-1,-1,-1): 
        text=""
        l=cacheConf[i][0]
        print(i,len(cacheConf))
        if i==(len(cacheConf)-1):
            text=shortQuestion
        else:
            nextI=i+1
            text=wordSalad+" "+shortQuestion if nextI==len(cacheConf)-2 else levels[i+1][2]
            text=Summary.summarizeText(text,min_length=l,max_length=l)
        embedding=EmbeddingsManager.new(text,"gpu")
        levels[i]=(embedding,cacheConf[i][1],text,EmbeddingsManager.embedding_function(embedding, text))
    
    cachePath=os.path.join(CONFIG["CACHE_PATH"],"smartcache")  
    if not os.path.exists(cachePath):
        os.makedirs(cachePath)
    for i in range(0,len(levels)):
        l=levels[i]
        isLast=i==len(levels)-1
        foundSub=False
        for f in os.listdir(cachePath):
            if not f.endswith(".bin"): continue
            embeddingPath=os.path.join(cachePath,f)
            answerPath=embeddingPath.replace(".bin",".json")
            subPath=embeddingPath.replace(".bin","")

            embedding=EmbeddingsManager.read(embeddingPath,group=EmbeddingsManager.GROUP_GPU)
            res=EmbeddingsManager.queryIndex(embedding,l[3],k=1,group=EmbeddingsManager.GROUP_GPU)
            score=res[0][1]
            print("Score:",score,"level score",l[1])
            if score<l[1]:
                print("Found in cache",l[2])
                if isLast:
                    print("Return from cache")
                    if os.path.exists(answerPath):                 
                        with open(answerPath, "r") as f:
                            answer=json.load(f)
                            return {
                                "answer":answer,
                                "writeAnswer":lambda x: None                          
                            }
                else:
                    print("Go deeper")
                    cachePath=subPath
                    foundSub=True
                    break
        if not foundSub:
            f=uuid.uuid4().hex+".bin"
            embeddingPath=os.path.join(cachePath,f)
            answerPath=embeddingPath.replace(".bin",".json")
            subPath=embeddingPath.replace(".bin","")
            if isLast:
                print("Not in cache!")
                def writeAnswer(answer):
                    print("Add answer to smart cache")
                    EmbeddingsManager.write(embeddingPath,l[0])
                    with open(answerPath, "w") as f:
                        json.dump(answer, f)
                return {
                    "answer":None,
                    "writeAnswer":writeAnswer
                }
            else:
                print("Create deeper level")
                os.mkdir(subPath)
                cachePath=subPath
                EmbeddingsManager.write(embeddingPath,l[0])

                

            





def queryChain(chain,question):
    shortQuestion=question
    
    if len(shortQuestion)>1024:
        shortQuestion=Summary.summarizeMarkdown(question,min_length=100,max_length=1024,withCodeBlocks=False)

    wordSalad=""
    for h in chain.memory.buffer: wordSalad+=h+" "
    wordSalad+=" "+question
        
    context=Summary.summarizeText(wordSalad,min_length=20,max_length=32)
    keywords=Summary.getKeywords(Summary.summarizeText(wordSalad,min_length=10,max_length=20))

    affineDocs=getAffineDocs(question,context,keywords,shortQuestion,wordSalad)
    print("Found ",len(affineDocs), " affine docs")
        
    
    print("Q: ", shortQuestion)

    output=None
    writeInCache=None
    if CONFIG.get("SMART_CACHE",None)!=None:
        cacheOutput=queryCache(wordSalad,shortQuestion,CONFIG.get("SMART_CACHE",None))
        if cacheOutput["answer"]!=None:
            output=cacheOutput["answer"]
        writeInCache=cacheOutput["writeAnswer"]

    if not output:
        output=chain({"input_documents": affineDocs, "question": shortQuestion}, return_only_outputs=True)    
        if writeInCache!=None:
            writeInCache(output)
    else: 
        print("Add cached output to history")
        chain.memory.buffer.append( "\n" + "QUESTION: " + question+"\n"+"ANSWER: " + output["output_text"])
        

    print("A :",output)
    return output


sessions={}
langchain.llm_cache = SQLiteCache(database_path=CONFIG["CACHE_PATH"]+"/langchain.db")

def clearSessions():
    while True:
        time.sleep(60*5)
        for session in sessions:
            if sessions[session]["timeout"] < time.time():
                del sessions[session]
threading.Thread(target=clearSessions).start()

def createSessionSecret():
    hex_chars = string.hexdigits
    timeHash=hashlib.sha256(str(time.time()).encode("utf-8")).hexdigest()[:12]
    return ''.join(secrets.choice(hex_chars) for i in range(64))+timeHash


app = Flask(__name__)    

@app.route("/langs")
def langs():
    return json.dumps(Translator.getLangs())

@app.route("/session",methods = ['POST'])
def session():
    body=request.get_json()
    lang=body["lang"] if "lang" in body  else "en"
    if lang=="auto":
        lang="en"


    if not "sessionSecret" in body or body["sessionSecret"].strip()=="":
        sessionSecret=createSessionSecret()
    else:
        sessionSecret=body["sessionSecret"]

    if sessionSecret not in sessions:
        sessions[sessionSecret]={
            "chain": createChain(),
            "timeout": time.time()+60*30
        }
    else:
        sessions[sessionSecret]["timeout"]=time.time()+60*30
    return json.dumps( {
        "sessionSecret": sessionSecret,
        "helloText":Translator.translate("en",lang,"Who are you?"),
        "welcomeText":Translator.translate("en", lang,"Hi there! I'm an AI assistant for the open source game engine jMonkeyEngine. I can help you with questions related to the jMonkeyEngine source code, documentation, and other related topics.")
    })

@app.route("/query",methods = ['POST'])
def query():
    try:
        body=request.get_json()
        question=rewrite(body["question"])
        lang=body["lang"] if "lang" in body  else "en"
        
        if lang == "auto":
            lang=Translator.detect(question)

        if lang!="en":
            question=Translator.translate(lang,"en",question)

        if len(question)==0:
            raise Exception("Question is empty")
        
        sessionSecret=body["sessionSecret"]   
        
        if sessionSecret not in sessions:
            return json.dumps({"error": "Session expired"})
            
        chain=sessions[sessionSecret]["chain"]

        output=queryChain(chain,question)
       
        if lang!="en":
            output["output_text"]=Translator.translate("en",lang,output["output_text"])

        #print(chain.memory.buffer)
        return json.dumps(output)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        errorStr=str(e)
        errorStr=rewriteError(errorStr)
        return json.dumps({"error": errorStr})


@app.route('/<path:filename>')
def serveFrontend(filename):
    return send_from_directory('frontend/', filename)

@app.route('/')
def serveIndex():
    return send_from_directory('frontend/', "index.html")





serve(app, host="0.0.0.0", port=8080)
