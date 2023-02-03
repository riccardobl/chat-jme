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
class Summary:
    summaryChain=None
    textSplitter=None


    @staticmethod
    def getKeywords(content):
        language = "en"
        max_ngram_size = 3
        deduplication_threshold = 0.9
        numOfKeywords = 5
        custom_kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, dedupLim=deduplication_threshold, top=numOfKeywords, features=None)
        keywords = custom_kw_extractor.extract_keywords(content)
        return [ t[0] for t in keywords]

    @staticmethod
    def summarizeComplex(content):
        try:
            if Summary.summaryChain==None:
                llm = OpenAI(temperature=0)
                Summary.summaryChain = load_summarize_chain(llm, chain_type="map_reduce")
                Summary.textSplitter = CharacterTextSplitter()
            texts = Summary.textSplitter.split_text(content)
            docs = [Document(page_content=t) for t in texts]
            out=Summary.summaryChain(docs, return_only_outputs=True)
            gc.collect()
            return out["output_text"]
        except Exception as e:
            print("Error summarizing with openAI. Fallback to others",e)
            return Summary.summarizeText(content,sentence_count=4)


    @staticmethod
    def summarizeMarkdown(content,url="",sentences_count=4, withCodeBlocks=True):
        content = mistune.html(content)
        content=Summary.summarizeHTML(content,url,sentences_count,withCodeBlocks)
        content = markdownify.markdownify(content, heading_style="ATX",autolinks=True,escape_asterisks=False,escape_underscores=False)

    @staticmethod
    def summarizeText(content,sentences_count=4):
        try:
            LANGUAGE="english"
            SENTENCES_COUNT = sentences_count
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

    @staticmethod
    def summarizeHTML(content,url="",sentences_count=4, withCodeBlocks=True):
        try:
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
            gc.collect()
            return text_summary
        except Exception as e:
            print("Error summarizing",e)
            gc.collect()
            return ""