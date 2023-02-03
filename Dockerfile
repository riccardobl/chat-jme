FROM python:3.11-bullseye

# SET ME
ENV OPENAI_API_KEY=""
###

ENV JME_HUB_URL="https://hub.jmonkeyengine.org"
ENV INDEX_PATH="/app/embeddings/"
ENV CACHE_PATH="/home/nonroot/.cache/"
ENV TRANSLATION_SERVICE="https://translate.frk.wf"
ENV JME_HUB_KNOWLEDGE_CUTOFF="2023-02-03"
ENV JME_HUB_SEARCH_FILTER="in:first order:likes"



ENV CONFIG_PATH="/app/config.json"
ENV CONDA_DIR /opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH

RUN mkdir -p /app&&mkdir -p /cache
ADD . /app

RUN apt-get update && \
apt-get install -y build-essential  && \
apt-get install -y wget cmake && \
apt-get clean && \
rm -rf /var/lib/apt/lists/* &&\
groupadd --gid 1000 nonroot&&\
useradd -m  --uid 1000 --gid 1000 nonroot&&\
chown nonroot:nonroot -Rf /app&&\
chown nonroot:nonroot -Rf /cache&&\
wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
/bin/bash /tmp/miniconda.sh -b -p /opt/conda &&\
rm /tmp/miniconda.sh 


WORKDIR /app
USER nonroot

RUN cd /app &&\
eval "$($CONDA_DIR/bin/conda shell.bash hook)"&&\
conda init bash &&\
conda env create --debug -f environment.yml &&\
conda activate jmebot&&\
conda clean --all --yes

RUN cd /app &&\
eval "$($CONDA_DIR/bin/conda shell.bash hook)"&&\
conda init bash &&\
conda activate jmebot&&\
pip --verbose install -r requirements.txt &&\
pip --verbose cache purge 

ENTRYPOINT [ "bash" , "/app/docker_entrypoint.sh" ]