from llama_index.core.node_parser import SimpleNodeParser


def build_nodes(documents):
    parser = SimpleNodeParser.from_defaults(
        chunk_size=512,
        chunk_overlap=50,
    )
    return parser.get_nodes_from_documents(documents)
