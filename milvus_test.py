import os
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection,utility
from transformers import AutoTokenizer, AutoModel, AutoModelForQuestionAnswering
import torch
import numpy as np
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

model_name = "paraphrase-multilingual-MiniLM-L12-v2"
model = SentenceTransformer(model_name, local_files_only=True)

print(f"111111111111!!!")
os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'
# 连接到Milvus
connections.connect("default", host="localhost", port="19530")

print(f"22222222222222!!!")
# 定义集合模式
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)  # 使用384维的向量
]

schema = CollectionSchema(fields, "Local Codebase Knowledge Base")
print(f"333333333333!!!")
def compare_fields(field1, field2):
    # 将 FieldSchema 对象转换为字典
    field1_dict = field1.to_dict()
    # 直接比较字典
    return field1_dict == field2

def ensure_collection_schema_matches(schema, existing_schema):
    if not all(compare_fields(f1, f2) for f1, f2 in zip(schema.fields, existing_schema["fields"])):
        utility.drop_collection("codebase_kb")
        print("Existing collection schema does not match. Dropping collection...")
    else:
        utility.drop_collection("codebase_kb")

if utility.has_collection("codebase_kb"):
    existing_schema = Collection("codebase_kb").describe()
    ensure_collection_schema_matches(schema, existing_schema)
collection = Collection("codebase_kb", schema)

def chunk_text(text, max_length=512):
    """
    将文本分割成不超过max_length个token的块，并保留50%的上下文token。
    :param text: 要分割的原始文本。
    :param max_length: 每个块的最大token数。
    :return: 包含文本块的列表。
    """
    tokens = model.tokenizer.tokenize(text)
    chunks = []
    current_chunk = []
    overlap_length = max_length // 10  # 50% overlap
    
    for token in tokens:
        current_chunk.append(token)
        if len(current_chunk) >= max_length - 2:
            chunks.append(''.join(current_chunk))
            # 保留后半部分作为下一个chunk的开始
            current_chunk = current_chunk[overlap_length:]
    
    # 添加最后一个chunk
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    return [chunk.strip() for chunk in chunks]

def get_file_embeddings(content):
    chunks = chunk_text(content)
    embeddings = model.encode(chunks)  # 对每个chunk进行编码
    return chunks, embeddings

def process_directory(directory):
    filenames = []
    embeddings = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):  # 假设只处理Python文件
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                chunks, chunk_embeddings = get_file_embeddings(content)
                filenames.extend([file_path] * len(chunks))
                embeddings.extend(chunk_embeddings)
    return filenames, embeddings

def create_index(collection):
    index_params = {
        "index_type": "IVF_FLAT",  # 尝试使用IVF_PQ索引类型
        "params": {"nlist": 128, "m": 8},  # 增加m参数
        "metric_type": "L2"
    }
    collection.create_index(field_name="embedding", index_params=index_params)

def insert_data_to_milvus(filenames, embeddings):
    entities = [
        filenames,
        embeddings
    ]
    collection.insert(entities)  # 插入数据到Milvus

    create_index(collection)

    collection.load()

def search_in_milvus(query, top_k=5):
    chunks, chunk_embeddings = get_file_embeddings(query)
    search_params = {"metric_type": "L2", "params": {"nprobe": 8}}
    results = collection.search(chunk_embeddings, "embedding", param=search_params, limit=top_k)
    for result in results:
        for id, distance in zip(result.ids, result.distances):
            print(f"ID: {id}, Distance: {distance}")
            # 获取文件名
            file_name = collection.query(expr=f"id == {id}", output_fields=["filename"])
            # 打印文件名和内容
            print(f"File Name: {file_name}")

# 假设你的代码库路径是'/path/to/codebase'
codebase_path = './'

# 处理目录并插入数据到Milvus
filenames, embeddings = process_directory(codebase_path)
insert_data_to_milvus(filenames, embeddings)

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