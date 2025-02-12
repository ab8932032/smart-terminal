import os
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility, Function, FunctionType
from transformers import AutoTokenizer, AutoModel, AutoModelForQuestionAnswering
import torch
import numpy as np
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer
import requests
import subprocess

model_name = "paraphrase-multilingual-MiniLM-L12-v2"
model = SentenceTransformer(model_name, local_files_only=True)

os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'

# 使用connections连接到Milvus
connections.connect("default", host="localhost", port="19530")
collection = None
def start_milvus_service():
    try:
        # 使用Docker命令启动已有的Milvus容器
        subprocess.run(["powershell.exe", "-Command", ".\\standalone.bat start"], check=True, shell=True)
        print("Milvus容器已启动")
    except subprocess.CalledProcessError as e:
        print(f"启动Milvus容器失败: {e}")

def initialize_milvus():
    if utility.has_collection("codebase_kb"):
        utility.drop_collection("codebase_kb")

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=1024, enable_analyzer=True),
        FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR, function=Function(
            name="bm25_func",
            input_field_names=["text"],
            output_field_names=["sparse"],
            function_type=FunctionType.BM25
        ),nullable=True)
    ]
    functions = [
        Function(
            name="text_bm25_emb",
            input_field_names=["text"],
            output_field_names=["sparse"],
            function_type=FunctionType.BM25,
        )
    ]
    schema = CollectionSchema(fields,"",functions)
    global collection
    collection = Collection(name="codebase_kb", schema=schema)

    index_params = {
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128, "m": 8},
        "metric_type": "L2"
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    index_params = {
        "index_type": "SPARSE_INVERTED_INDEX",
        "metric_type": "IP"
    }
    collection.create_index(field_name="sparse", index_params=index_params)

    collection.load()

def chunk_text(text, max_length=512, text_length=1024):
    """
    将文本分割成不超过max_length个token的块，并保留10%的上下文token。
    :param text: 要分割的原始文本。
    :param max_length: 每个块的最大token数。
    :param text_length: 总文本的最大长度。
    :return: 包含文本块的列表、嵌入向量列表和稀疏嵌入向量列表。
    """
    tokens = model.tokenizer.tokenize(text)
    chunks = []
    embeddings = []
    current_chunk = []
    overlap_length = max_length // 10  # 10% overlap
    total_length=0
    for token in tokens:
        total_length += len(token.encode('utf-8'))
        if total_length > text_length:
            chunk = ''.join(current_chunk).strip()
            chunks.append(chunk)
            embeddings.append(model.encode(chunk))
            # 保留后半部分作为下一个chunk的开始
            current_chunk = current_chunk[max_length-overlap_length:]
            total_length = len(''.join(current_chunk).strip().encode('utf-8'))
        else:
            current_chunk.append(token)
            if len(current_chunk) >= max_length - 2:
                chunk = ''.join(current_chunk).strip()
                chunks.append(chunk)
                embeddings.append(model.encode(chunk))
                # 保留后半部分作为下一个chunk的开始
                current_chunk = current_chunk[max_length-overlap_length:]
                total_length = len(''.join(current_chunk).strip().encode('utf-8'))
    
    # 添加最后一个chunk
    if current_chunk:
        chunk = ''.join(current_chunk).strip()
        chunks.append(chunk)
        embeddings.append(model.encode(chunk))
    
    return chunks, embeddings

def process_directory(directory):
    filenames = []
    texts = []
    embeddings = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):  # 假设只处理Python文件
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                chunks, chunk_embeddings = chunk_text(content)
                filenames.extend([file_path] * len(chunks))
                texts.extend(chunks)
                embeddings.extend(chunk_embeddings)
    return filenames, texts, embeddings

def insert_data_to_milvus(filenames, texts, embeddings):
    entities = []
    for i in range(len(embeddings)):
        entities.append({'filename':filenames[i],'embedding':embeddings[i],'text':texts[i]})
        #打印filename和text的长度
        print(f"filename: {filenames[i]}")
        print(f"text: {len(texts[i].encode('utf-8'))}")
    global collection  # 确保collection是全局变量
    collection.insert(entities)  # 使用MilvusClient的insert方法

def search_in_milvus(query, top_k=5):
    chunks, chunk_embeddings = chunk_text(query)
    search_params = {"metric_type": "L2", "params": {"nprobe": 8}}
    results = collection.search(
        data=chunk_embeddings,
        anns_field="embedding",
        param=search_params,
        limit=top_k
    )  # 使用Collection的search方法

    if results and len(results) > 0:
        for result in results:
            if len(result) > 0:
                for id, distance in zip(result.ids, result.distances):
                    print(f"ID: {id}, Distance: {distance}")
                    # 获取文件名
                    file_name = collection.query(expr=f"id == {id}", output_fields=["filename"])  # 使用Collection的query方法
                    # 打印文件名和内容
                    print(f"File Name: {file_name}")

    print(f"=====================================================================!!!")
    search_params = {'params': {'drop_ratio_search': 0.2}}
    results2 = collection.search(
        data=chunks,
        anns_field="sparse",
        param=search_params,
        limit=top_k
    )  # 使用Collection的search方法
    if results2 and len(results2) > 0:
        for result in results2:
            if len(result) > 0:
                for id, distance in zip(result.ids, result.distances):
                    print(f"ID: {id}, Distance: {distance}")
                    # 获取文件名
                    file_name = collection.query(expr=f"id == {id}", output_fields=["filename"])  # 使用Collection的query方法
                    # 打印文件名和内容
                    print(f"File Name: {file_name}")

start_milvus_service()

initialize_milvus()

# 假设你的代码库路径是'/path/to/codebase'
codebase_path = '.\\'

# 处理目录并插入数据到Milvus
filenames, texts, embeddings = process_directory(codebase_path)
insert_data_to_milvus(filenames, texts, embeddings)

print(f"start!!!")
# 示例查询
search_query = "CommandProcessor"
search_in_milvus(search_query, top_k=1)

print(f"start1111!!!")
search_query = "CommandProcessor"
#search_in_milvus(search_query, top_k=5)

print(f"start12222!!!")
search_query = "我是一只猪"
search_in_milvus(search_query, top_k=20)
