

## API


### Create maintain a session (should be called periodically)
**POST** /session

REQUEST
```
{
    "sessionSecret:"", // sessionSecret of the session to maintain or nothing to create a new one
    "lang":"en"// || "it" || etc... || "auto",    
}
```
RESPONSE
```
{
    sessionSecret:"XYZ", // sessionSecret of the session
    "helloText":"???" // Text that can be used to initiate a conversation with the bot (in the chosen language)
}
```

### Ask something
**POST** /query

REQUEST
```
{
    "sessionSecret:"",
    "lang":"en"// || "it" || etc... || "auto",
    "question":"Your question"
}

```
RESPONSE
```
{
    "output_text":"???" // Answer to the question
}
```

### List all supported languages
**GET** /lang

RESPONSE
```
[
    {
        name:"English",
        code:"en"
    },
    {
        name:"Italian",
        code:"it"
    },
    ...
]