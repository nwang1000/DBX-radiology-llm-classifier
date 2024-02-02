# Databricks notebook source
#install libraries
!pip install -q accelerate==0.21.0 peft==0.4.0 bitsandbytes==0.40.2 transformers==4.31.0 trl==0.4.7 guardrail-ml==0.0.12
!pip install -q unstructured["local-inference"]==0.7.4 pillow
!pip install pydantic==1.8.2 
!pip install -q transformers[deepspeed] mpi4py

# COMMAND ----------

#import libraries
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftConfig, PeftModel

# COMMAND ----------

#base model
model_name = 'epfl-llm/meditron-7b'

# COMMAND ----------

#model weights
output_dir = '/Volumes/ang_nara_catalog/rad_llm/results'

# COMMAND ----------

#device map
device_map = {"": 0}

# COMMAND ----------

# MAGIC %md # Option1: Push Model to Hugging Face

# COMMAND ----------

val = dbutils.secrets.get(scope="medtron-hf-token", key="token")

# COMMAND ----------

#TODO replace with secrets and require 
!huggingface-cli login --token $val

# COMMAND ----------

# Reload model in FP16 and merge it with LoRA weights
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    low_cpu_mem_usage=True,
    return_dict=True,
    torch_dtype=torch.float16,
    device_map=device_map,
)
model = PeftModel.from_pretrained(base_model, output_dir)
model = model.merge_and_unload()

# Reload tokenizer to save it
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# COMMAND ----------

#push model and tokemizer to hf
model.push_to_hub("RadiologyLLMs/RadLlama2-7b", use_auth_token=True, create_pr=1, max_shard_size='20GB')
tokenizer.push_to_hub("RadiologyLLMs/RadLlama2-7b", use_auth_token=True, create_pr=1)

# COMMAND ----------

# MAGIC %md # Option2: Push Model to UC Volume (Recommended)

# COMMAND ----------

#push model and tokemizer to volume
model.save_pretrained("/Volumes/ang_nara_catalog/rad_llm/results/model")
tokenizer.save_pretrained("/Volumes/ang_nara_catalog/rad_llm/results/model")
