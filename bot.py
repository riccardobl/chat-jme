import os
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
import langchain
from langchain.cache import InMemoryCache
from langchain.llms import OpenAI
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory,ConversationBufferMemory,ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from embeddings import Embeddings
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

INDEX_PATH="index/"
CACHE_PATH="langchain.db"


def getIndices():
    parts=[os.path.join(INDEX_PATH, file) for file in os.listdir(INDEX_PATH)]
    loaded_parts = []
    for part in parts:
        try:
            loaded_parts.append(Embeddings.read(part))
        except Exception as e:
            print("Error loading", part, e)
            continue    
    return  loaded_parts
    
def rewriteError(error):
    if error.startswith("Rate limit reached ") :
        return "Rate limit."

def rewrite(question):
    # replace app, applet, game, application with simple application 
    question=re.sub(r"\b(app|applet|game|application)\b", "simple application", question)
    return question


def createChain():
    template = """You are an AI assistant for the open source game engine jMonkeyEngine. 
The documentation is located at https://wiki.jmonkeyengine.org . 
The source code is located at this github repository https://github.com/jMonkeyEngine/jmonkeyengine/ .
In the answer includes a code snippet as an example.
If the question is not about jMonkeyEngine, politely inform them that you are tuned to only answer questions about jMonkeyEngine,
unless the human asks for a good night story, in that case make up a story.
If you don't know the answer, just say "Hmm, I'm not sure." Don't try to make up an answer.
If the human thanks you, say that you are welcome.

When replying please consider these important rules:
- Applets are not supported anymore so don't answer things related to Applets.
- When the question contains "show me the code", write a code snippet in the answer.
- IOs is not supported anymore so don't answer things related to IOs.
- You can use any code from github and the documentation

Given the following extracted parts of a long document and a question, create a conversational final answer with references ("SOURCES"). 
If you don't know the answer, just say that you don't know. ALWAYS return a new line and then the "SOURCES" part in your answer.

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
    #memory = ConversationBufferMemory(human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    # memory = ConversationBufferWindowMemory(human_prefix="QUESTION: ",ai_prefix="FINAL ANSWER in Markdown: ", memory_key="history", input_key="question", k=4)
    memory=ConversationSummaryBufferMemory(llm=OpenAI(), max_token_limit=1024,human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    # llm = OpenAI(temperature=0, model_name="text-davinci-003")
    chain = load_qa_with_sources_chain(
        OpenAI(
            temperature=0.0,
            model_name="text-davinci-003",
            max_tokens=2248,
        ), 
        memory=memory, 
        prompt=prompt, 
        verbose=True
    )
    return chain


sessions={}
#langchain.llm_cache = InMemoryCache()
langchain.llm_cache = SQLiteCache(database_path=CACHE_PATH)

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


    if not "sessionSecret" in body:
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
        "helloText":Translator.translate("en",lang,"Introduce yourself")
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
        
        affineDocs=Embeddings.query(getIndices(),question)
        print("Found ",len(affineDocs), " affine docs")
        
        print("Q: ", question)
        output=chain({"input_documents": affineDocs, "question": question}, return_only_outputs=True)
        
        if lang!="en":
            output["output_text"]=Translator.translate("en",lang,output["output_text"])

        print(output)
        print(chain.memory.buffer)
        return json.dumps(output)
    except Exception as e:
        errorStr=str(e)
        errorStr=rewriteError(errorStr)
        print(errorStr)
        return json.dumps({"error": errorStr})

# serve static files from ./frontend
@app.route('/<path:filename>')
def serveFrontend(filename):
    return send_from_directory('frontend/', filename)

@app.route('/')
def serveIndex():
    return send_from_directory('frontend/', "index.html")



serve(app, host="0.0.0.0", port=8080)
