# Databricks notebook source
# MAGIC %md # Notebook Parameters

# COMMAND ----------

dbutils.widgets.text("catalog", "hls_healthcare") 
dbutils.widgets.text("database", "hls_dev")
dbutils.widgets.text("model_version", "1")

# COMMAND ----------

batch_tablename = (dbutils.widgets.get("catalog") + 
                    "." + dbutils.widgets.get("database") +
                    ".batch_prediction_result")
                    
eval_table = (dbutils.widgets.get("catalog") + 
                    "." + dbutils.widgets.get("database") +
                    ".batch_pred_eval") 
                  
incorrect_pred_table = (dbutils.widgets.get("catalog") + 
                    "." + dbutils.widgets.get("database") +
                    ".batch_incorrec_pred") 
                  
model_version = dbutils.widgets.get("model_version")
MODEL_NAME = dbutils.widgets.get("catalog") + "." + dbutils.widgets.get("database") + ".rad-meditron"

# COMMAND ----------

#install libraries
!pip install -q accelerate==0.21.0 peft==0.4.0 bitsandbytes==0.40.2 transformers==4.31.0 trl==0.4.7 guardrail-ml==0.0.12
!pip install -q unstructured["local-inference"]==0.7.4 pillow
!pip install pydantic==1.8.2
!pip install --upgrade mlflow 
!pip install sentence-transformers

# COMMAND ----------

import os
import torch
import pandas as pd
import re
import mlflow
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    HfArgumentParser,
    TrainingArguments,
    pipeline,
    logging,
)
from peft import LoraConfig, PeftModel, get_peft_model
from trl import SFTTrainer
from pyspark.sql.functions import udf,col
import pyspark.sql.functions as F
from pyspark.sql.types import DoubleType, StringType
from sentence_transformers import SentenceTransformer, util

# COMMAND ----------

test_data = spark.table(batch_tablename)

# COMMAND ----------

# Load pyfunc model from UC
mlflow.set_registry_uri("databricks-uc")
model_uri = "models:/{model_name}/{model_version}".format(model_name=MODEL_NAME, model_version=model_version)
model =  mlflow.pyfunc.load_model(model_uri)

# COMMAND ----------

# Load pre-trained BERT model
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

# Define a UDF to calculate similarity
@udf(DoubleType())
def calculate_similarity(ground_truth, predictions):
    embeddings_ground_truth = model.encode([ground_truth])[0]
    embeddings_predictions = model.encode([predictions])[0]
    return float(util.pytorch_cos_sim(embeddings_ground_truth, embeddings_predictions).cpu().numpy().diagonal()[0])

# Apply the UDF to calculate similarity and add a new column
test_data = test_data.withColumn('semantic_similarity', calculate_similarity(test_data['ground_truth'], test_data['predictions']))

for c_name, c_type in test_data.dtypes:
    if c_type in ('double', 'float'):
        test_data = test_data.withColumn(c_name, F.round(c_name, 2))

# COMMAND ----------

test_data.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(eval_table)

# COMMAND ----------

filtered_dataframe = test_data.filter(col("semantic_similarity") < 0.50)

# Write the filtered DataFrame to the Delta table
filtered_dataframe.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(incorrect_pred_table)

# COMMAND ----------

#TODO add stats / visuals here to easily consume output
