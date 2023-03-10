FROM ubuntu:22.04

# SET ME
ENV OPENAI_API_KEY=""
###

ENV JME_HUB_URL="https://hub.jmonkeyengine.org"
ENV INDEX_PATH="/app/embeddings/"
ENV CACHE_PATH="/home/nonroot/.cache/"
ENV TRANSLATION_SERVICE="https://translate.frk.wf"
ENV JME_HUB_KNOWLEDGE_CUTOFF="2023-02-03"
ENV JME_HUB_SEARCH_FILTER="in:first order:likes"
ENV DEVICE="cpu"
ENV USE_SUMY="true"
ENV OPENAI_MODEL="text-davinci-003"


ENV CONFIG_PATH="/app/config.json"
ENV CONDA_DIR /home/nonroot/miniconda3
ENV PATH=$CONDA_DIR/bin:$PATH

COPY environment.yml /tmp/environment.yml
COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && \
apt-get install -y wget git && \
apt-get clean && \
rm -rf /var/lib/apt/lists/* &&\
mkdir -p /app&&\
groupadd --gid 1000 nonroot&&\
useradd -m  --uid 1000 --gid 1000 nonroot&&\
chown nonroot:nonroot -Rf /app

WORKDIR /app
USER nonroot

RUN cd /tmp&&\
wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
/bin/bash /tmp/miniconda.sh -b  &&\
rm /tmp/miniconda.sh &&\
cd /tmp &&\
eval "$($CONDA_DIR/bin/conda shell.bash hook)"&&\
conda init bash &&\
conda env create  -f environment.yml &&\
conda activate jmebot&&\
pip --verbose install -r requirements.txt &&\
pip --verbose cache purge &&\
conda clean --all --yes

USER root
ADD . /app
RUN chown nonroot:nonroot -Rf /app

USER nonroot
ENTRYPOINT [ "bash" , "/app/docker_entrypoint.sh" ]