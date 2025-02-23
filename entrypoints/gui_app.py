import tkinter as tk
from adapters.frontends.tkinter_gui import TkinterFrontend
from utils.config_loader import ModelConfig
from core.qa_engine import QAEngine
from utils.text_processing import TextProcessor
from adapters.vectordb.milvus_adapter import MilvusManager
from core.retrieval_service import RetrievalService

def launch_gui():
    ModelConfig.load()
    
    db_manager = MilvusManager(ModelConfig.get['vectordb'])
    retrieval_service = RetrievalService(db_manager)
    text_processor = TextProcessor(ModelConfig.get['text_processing'])
    qa_engine = QAEngine(ModelConfig.get['qa_model'])
    root = tk.Tk()
    app = TkinterFrontend(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()