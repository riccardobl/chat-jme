from sumy.parsers.html import HtmlParser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
from bs4 import BeautifulSoup
import gc
import mistune
import markdownify
from langchain import OpenAI, PromptTemplate, LLMChain
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains.mapreduce import MapReduceChain
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
import yake
from transformers import pipeline

from urllib.parse import urljoin
class Summary:
    #summaryChain=None
    #textSplitter=None
    summarizer=None
    CONFIG=None
    @staticmethod
    def init(CONFIG):
        Summary.useGPU=CONFIG.get("DEVICE","cpu")=="gpu" or CONFIG.get("DEVICE","cpu")=="cuda"
        Summary.CONFIG=CONFIG
        Summary.useSumy=CONFIG.get("USE_SUMY",False)
        if not Summary.useSumy:
            if Summary.summarizer==None:
                print("Preloading flan-t5-base-samsum")
                Summary.summarizer = pipeline("summarization", model='philschmid/flan-t5-base-samsum', device=0 if Summary.useGPU else -1)
                print("Done")

        # if Summary.qa==None:
        #     Summary.qa = pipeline("question-answering", model='distilbert-base-cased-distilled-squad')

    # @staticmethod
    # def getTopic(content,min_length=10,max_length=100):
    #     return Summary.summarizer(content,min_length=min_length,max_length=max_length)["summary_text"]

    # @staticmethod
    # def ask(content,question):
    #     result=Summary.qa(question=question, context=content)
    #     return result['answer']

    @staticmethod
    def getKeywords(content,n=5):
        language = "en"
        max_ngram_size = 3
        deduplication_threshold = 0.9
        numOfKeywords = n
        custom_kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, dedupLim=deduplication_threshold, top=numOfKeywords, features=None)
        keywords = custom_kw_extractor.extract_keywords(content)
        return [ t[0] for t in keywords]

    # @staticmethod
    # def summarizeComplex(content,min_length=10,max_length=100):
    #     #device=Summary.CONFIG.get("DEVICE","openai")
    #     # if device=="gpu" or device=="cuda" or device=="cuda":
    #     return Summary.summarizer(content,min_length=min_length,max_length=max_length)["summary_text"]
        # else:
        #     try:
        #         if Summary.summaryChain==None:
        #             llm = OpenAI(temperature=0)
        #             Summary.summaryChain = load_summarize_chain(llm, chain_type="map_reduce")
        #             Summary.textSplitter = CharacterTextSplitter()
        #         texts = Summary.textSplitter.split_text(content)
        #         docs = [Document(page_content=t) for t in texts]
        #         out=Summary.summaryChain(docs, return_only_outputs=True)
        #         gc.collect()
        #         return out["output_text"]
        #     except Exception as e:
        #         print("Error summarizing with openAI. Fallback to others",e)
        #         return Summary.summarizeText(content,sentence_count=4)


    @staticmethod
    def summarizeMarkdown(content,url="",min_length=10,max_length=100, withCodeBlocks=True):
        content = mistune.html(content)
        content=Summary.summarizeHTML(content,url,min_length,max_length,withCodeBlocks)
        content = markdownify.markdownify(content, heading_style="ATX",autolinks=True,escape_asterisks=False,escape_underscores=False)

    @staticmethod
    def summarizeText(content,min_length=10,max_length=100):       
        if Summary.useSumy:
            try:
                LANGUAGE="english"
                SENTENCES_COUNT = max_length
                stemmer = Stemmer(LANGUAGE)
                summarizer = Summarizer(stemmer)
                summarizer.stop_words = get_stop_words(LANGUAGE)
                parser = PlaintextParser.from_string(content, Tokenizer(LANGUAGE))
                text_summary=""
                for sentence in summarizer(parser.document, SENTENCES_COUNT):
                    text_summary+=str(sentence)
                gc.collect()
                return text_summary
            except Exception as e:
                print("Error summarizing",e)
                gc.collect()
                return ""
        else:
            contentLen=len(content)
            if contentLen<min_length:
                return content
            if max_length>contentLen:
                max_length=contentLen
            
            res=Summary.summarizer(content,min_length=min_length,max_length=max_length)
            return res[0]["summary_text"]

    @staticmethod
    def summarizeHTML(content,url="",min_length=10,max_length=100, withCodeBlocks=True):
        
        

        try:
            # LANGUAGE="english"
            # SENTENCES_COUNT = sentences_count
            # stemmer = Stemmer(LANGUAGE)
            # summarizer = Summarizer(stemmer)
            # summarizer.stop_words = get_stop_words(LANGUAGE)
            # parser = HtmlParser.from_string(content, url=url,tokenizer=Tokenizer(LANGUAGE))
            # text_summary=""
            # for sentence in summarizer(parser.document, SENTENCES_COUNT):
            #     text_summary+=str(sentence)
        
            # Extract links
            soup = BeautifulSoup(content, 'html.parser')
            for link in soup.find_all('a'):
                href = link.get('href')
                url = urljoin(url, href)
                link.string = url

            # Extract code blocks
            codeBlocks=""
            cc=soup.find_all("pre")
            for c in cc:
                if withCodeBlocks:
                    i=0
                    i+=1
                    rpl=f"[{i}]"
                    codeBlocks+=rpl+" <pre><code>"
                    codeBlocks+=c.text
                    codeBlocks+="</code></pre>"            
                    c.string = rpl
                else:
                    c.string = ""
                
            # To plain text
            texts = soup.findAll(text=True)
            text_summary = u" ".join(t.strip() for t in texts)
            text_summary=Summary.summarizeText(text_summary,min_length,max_length)
            text_summary+=codeBlocks

            gc.collect()
            return text_summary
        except Exception as e:
            print("Error summarizing",e)
            gc.collect()
            return ""