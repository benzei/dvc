#!/bin/bash

set -e

# 1. First ML model

mkdir myrepo
cd myrepo

git init
echo "This is an empty readme" > README.md
git add README.md
git commit -m 'add readme'

git checkout -b first_model
mkdir code
wget -nv -P code/ https://s3-us-west-2.amazonaws.com/dvc-share/so/code/featurization.py \
        https://s3-us-west-2.amazonaws.com/dvc-share/so/code/evaluate.py \
        https://s3-us-west-2.amazonaws.com/dvc-share/so/code/train_model.py \
        https://s3-us-west-2.amazonaws.com/dvc-share/so/code/split_train_test.py \
        https://s3-us-west-2.amazonaws.com/dvc-share/so/code/xml_to_tsv.py \
        https://s3-us-west-2.amazonaws.com/dvc-share/so/code/requirements.txt
#pip install -U -r code/requirements.txt
# Edit eval file format
git add code/
git commit -m 'Download code'


dvc init
dvc import https://s3-us-west-2.amazonaws.com/dvc-share/so/100K/Posts.xml.tgz data/
dvc run tar zxf data/Posts.xml.tgz -C data/

dvc run python code/xml_to_tsv.py data/Posts.xml data/Posts.tsv python
dvc run python code/split_train_test.py data/Posts.tsv 0.33 20170426 data/Posts-train.tsv data/Posts-test.tsv
dvc run python code/featurization.py data/Posts-train.tsv data/Posts-test.tsv data/matrix-train.p data/matrix-test.p

dvc run python code/train_model.py data/matrix-train.p 20170426 data/model.p

dvc run python code/evaluate.py data/model.p data/matrix-test.p data/eval_auc.txt

dvc target data/eval_auc.txt
cat data/eval_auc.txt
# AUC: 0.645320


git checkout -b input_25K # <--
dvc remove data/Posts.xml.tgz
dvc import https://s3-us-west-2.amazonaws.com/dvc-share/so/25K/Posts.xml.tgz data/
dvc repro
cat data/eval_auc.txt
# 0.596182
vi code/train_model.py  # estimators=500
git commit -am 'estimators=500'
dvc repro
cat data/eval_auc.txt
# 0.619262
vi code/featurization.py
git commit -am 'Add bigrams'
dvc repro
cat data/eval_auc.txt
# 0.628989
vi code/featurization.py
git commit -am 'Add three-grams'
dvc repro
cat data/eval_auc.txt
# 0.630682
vi code/featurization.py
git commit -am 'Add 4-grams'
dvc repro
cat data/eval_auc.txt
# 0.621002

git checkout 2195f1032 -b three_grams # <--
dvc repro # not needed
cat data/eval_auc.txt
# 0.630682

git checkout first_model
git merge three_grams
dvc repro



vi code/featurization.py
# 0.578447



# 2. Reproduce: change input dataset

dvc remove data/Posts.xml.tgz
#dvc import https://s3-us-west-2.amazonaws.com/dvc-share/so/100K/Posts.xml.tgz data/
dvc import https://s3-us-west-2.amazonaws.com/dvc-share/so/25K/Posts.xml.tgz data/
dvc repro data/evaluation.txt
cat data/evaluation.txt
# AUC: 0.639861

# 3. Share your research

# Improve features
echo " " >> code/featurization.py
git add code/featurization.py
git commit -m 'Include bigram'
dvc repro data/evaluation.txt
cat data/evaluation.txt
