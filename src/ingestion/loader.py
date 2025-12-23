from llama_index.core import SimpleDirectoryReader


def load_documents(path: str = "data/raw"):
    return SimpleDirectoryReader(path).load_data()
