# CHAT-JME
An AI assistant for jMonkeyEngine and related projects.

It knows :
- all the main documentation of jMonkeyEngine and some prominent projects
- the entire source code of the jMonkeyEngine main repo
- how to search the forum for basic queries

For more details, check the [knowledge base](#knowledge-base) section.


## Technologies
To provide the functionality of the bot, the following libraries are used:

- [🦜🔗 LangChain](https://github.com/hwchase17/langchain): to interface with GPT-3
- [OpenAI apis](https://openai.com/api/): LLM for text generation, embeddings and summarization 
- [MiniLM L6 v2](https://huggingface.co/sentence-transformers/paraphrase-MiniLM-L6-v2): fast embeddings 
- [Sumy](https://github.com/miso-belica/sumy): Summarization 
- [Yake](https://pypi.org/project/yake/): keywords extraction 
- [LibreTranslate](https://libretranslate.com/): Multi language support and detection
- and more .. Check the [requirements.txt](requirements.txt) and [environment.yml](environment.yml) for the full list.


## Knowledge base
The bot extends the knowledge of GPT-3 by embedding pieces of information from the following sources:

### Static embeddings
Static embeddings are updated periodically and stored in the [embeddings/](embeddings/) folder in this repo.

- [x] [jmonkeyengine.org](https://jmonkeyengine.org) (partial)
- [x] [jMonkeyEngine Wiki](wiki.jmonkeyengine.org) 
- [x] [jMonkeyEngine source code](https://github.com/jMonkeyEngine/jmonkeyengine/) 
- [x] [Minie Wiki](https://stephengold.github.io/Minie/minie) 
- [ ] [Minie source code]() 
- [x] [Lemur Wiki](https://github.com/jMonkeyEngine-Contributions/Lemur/wiki)
- [ ] [Lemur source code]()
- [x] [Zay-ES wiki](https://github.com/jMonkeyEngine-Contributions/zay-es/wiki)
- [ ] [Zay-ES source code]()

### Dynamic embeddings
Dynamic embeddings are generated on the fly for the requested information.

- [x] [jMonkeyEngine Hub](https://hub.jmonkeyengine.org/) (simple search queries based on keywords, cut off: 2023-02-03 )



## Build and run

In a docker host

### Build
```bash
docker build -t chat-jme .
```

### Run
```bash
mkdir -p /srv/chat-jme/cache
chown -Rf 1000:1000 /srv/chat-jme/cache 

docker run -d --restart=always \
-eOPENAI_API_KEY="XXXXXXXX" \
-v/srv/chat-jme/cache:/home/nonroot/.cache \
-p8080:8080 \
--name="chat-jme" \
chat-jme bot
```
*To use custom static embeddings specify the INDEX_PATH environment variable*
**NOTE: the first run might take some time since it has to download the models.**

### Rebuild/update static embeddings
```bash
mkdir -p /srv/chat-jme/cache
chown -Rf 1000:1000 /srv/chat-jme/cache 

mkdir -p /srv/chat-jme/embeddings
chown -Rf 1000:1000 /srv/chat-jme/embeddings

docker run -d --restart=always \
-eOPENAI_API_KEY="XXXXXXXX" \
-eINDEX_PATH="/embeddings" \
-v/srv/chat-jme/cache:/home/nonroot/.cache \
-v/srv/chat-jme/embeddings:/embeddings \
--name="chat-jme" \
chat-jme ingest
```



## API


### Create maintain a session (should be called periodically)
**POST** /session

REQUEST
```json
{
    "sessionSecret":"", // sessionSecret of the session to maintain or nothing to create a new one
    "lang":"en" // || "it" || etc... || "auto",    
}
```
RESPONSE
```json
{
    "sessionSecret":"XYZ", // sessionSecret of the session
    "helloText":"???", // Text that can be used to initiate a conversation with the bot (in the chosen language)
    "welcomeText": "..." // Hardcoded welcome text in the specified language
}
```

### Ask something
**POST** /query

REQUEST
```json
{
    "sessionSecret":"",
    "lang":"en",// || "it" || etc... || "auto",
    "question":"Your question"
}

```
RESPONSE
```json
{
    "output_text":"???" // Answer to the question
}
```

### List all supported languages
**GET** /lang

RESPONSE
```json
[
    {
        "name":"English",
        "code":"en"
    },
    {
        "name":"Italian",
        "code":"it"
    },
    ...
]
```


## Frontend usage and configuration

The frontend is server on the 8080 port by default.
It supports some configuration parameters that can be passed as document hash parameters.
Multiple parameters can be concatenated with the `&` character.

- **lang** the language for questions and answers. (default: en, use auto to get the bot to detect the language automatically)
- **compact** if true, the bot will be displayed in a compact mode, good for embedding (default: false)

 
