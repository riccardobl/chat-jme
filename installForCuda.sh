set -e

cdir="$PWD"
eval "$($CONDA_DIR/bin/conda shell.bash hook)"
conda init bash 

while [ "$CONDA_PREFIX" != "" ]; do
    conda deactivate
done

conda activate jmebot

# Install cuda deps
conda install --yes cuda-toolkit=11.7  pytorch-cuda=11.7 -c pytorch -c nvidia  -c "nvidia/label/cuda-11.7.0" 
pip uninstall --yes faiss-cpu

# Build faiss-gpu (prebuilt faiss-gpu is not currently available for python>3.9)
cd /tmp

conda deactivate
export CUDA_HOME=/usr/local/cuda-11
export FAISS_ENABLE_GPU=ON
export PATH="/usr/local/cuda-11/bin:$PATH"
 
rm -Rf faiss||true
git clone https://github.com/facebookresearch/faiss.git --depth 1 --branch v1.7.3

cd faiss


conda install --yes -c conda-forge libstdcxx-ng

PYTHON_EXECUTABLE="$(which python)"
if [ "$PYTHON_EXECUTABLE" != "" ]; then
        pyVersion=$(python -c 'import sys; print(sys.version_info[0])')
        if [ "$pyVersion" != "3" ]; then
                PYTHON_EXECUTABLE=""
        fi
fi

if [ "$PYTHON_EXECUTABLE" = "" ]; then
    PYTHON_EXECUTABLE=$(which python3)
fi

cmake -B build \
        -DPython_EXECUTABLE="$PYTHON_EXECUTABLE" \
        -DCMAKE_CUDA_ARCHITECTURES="60;75"\
        -DFAISS_ENABLE_GPU=ON \
        -DFAISS_ENABLE_C_API=ON \
        -DFAISS_ENABLE_PYTHON=ON \
        -DBUILD_TESTING=OFF \
         -DFAISS_OPT_LEVEL=avx2  \
         -DCMAKE_BUILD_TYPE=Release \
        .

if [ "$MAKE_FLAGS" = "" ]; then
        MAKE_FLAGS=" -j$(nproc) "
fi

make  -C build $MAKE_FLAGS

conda activate jmebot
cd build/faiss/python 
python3 setup.py build
python3 setup.py install

cd "$cdir"


