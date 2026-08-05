# Details

Date : 2026-08-05 15:19:57

Directory /Volumes/data/projects/poxenstudio/MyNexus/worker

Total : 34 files,  1910 codes, 266 comments, 416 blanks, all 2592 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [worker/Dockerfile](/worker/Dockerfile) | Docker | 20 | 0 | 5 | 25 |
| [worker/requirements.txt](/worker/requirements.txt) | pip requirements | 8 | 0 | 1 | 9 |
| [worker/src/config.py](/worker/src/config.py) | Python | 85 | 17 | 29 | 131 |
| [worker/src/grpc\_client.py](/worker/src/grpc_client.py) | Python | 46 | 14 | 10 | 70 |
| [worker/src/mynexus\_pb2.py](/worker/src/mynexus_pb2.py) | Python | 77 | 8 | 7 | 92 |
| [worker/src/mynexus\_pb2.pyi](/worker/src/mynexus_pb2.pyi) | Python | 189 | 0 | 22 | 211 |
| [worker/src/mynexus\_pb2\_grpc.py](/worker/src/mynexus_pb2_grpc.py) | Python | 521 | 81 | 47 | 649 |
| [worker/src/nodes/base.py](/worker/src/nodes/base.py) | Python | 10 | 1 | 5 | 16 |
| [worker/src/nodes/cleaners/base\_cleaner.py](/worker/src/nodes/cleaners/base_cleaner.py) | Python | 6 | 1 | 5 | 12 |
| [worker/src/nodes/cleaners/whitespace\_cleaner.py](/worker/src/nodes/cleaners/whitespace_cleaner.py) | Python | 20 | 2 | 11 | 33 |
| [worker/src/nodes/embedders/base\_embedder.py](/worker/src/nodes/embedders/base_embedder.py) | Python | 9 | 1 | 6 | 16 |
| [worker/src/nodes/embedders/ollama\_embedder.py](/worker/src/nodes/embedders/ollama_embedder.py) | Python | 40 | 3 | 12 | 55 |
| [worker/src/nodes/embedders/openai\_embedder.py](/worker/src/nodes/embedders/openai_embedder.py) | Python | 46 | 5 | 14 | 65 |
| [worker/src/nodes/factory.py](/worker/src/nodes/factory.py) | Python | 24 | 0 | 7 | 31 |
| [worker/src/nodes/llm/base\_llm.py](/worker/src/nodes/llm/base_llm.py) | Python | 7 | 1 | 5 | 13 |
| [worker/src/nodes/llm/ollama\_llm.py](/worker/src/nodes/llm/ollama_llm.py) | Python | 42 | 3 | 11 | 56 |
| [worker/src/nodes/llm/openai\_llm.py](/worker/src/nodes/llm/openai_llm.py) | Python | 50 | 4 | 11 | 65 |
| [worker/src/nodes/parsers/base\_parser.py](/worker/src/nodes/parsers/base_parser.py) | Python | 11 | 6 | 6 | 23 |
| [worker/src/nodes/parsers/epub\_parser.py](/worker/src/nodes/parsers/epub_parser.py) | Python | 49 | 2 | 15 | 66 |
| [worker/src/nodes/parsers/registry.py](/worker/src/nodes/parsers/registry.py) | Python | 12 | 1 | 6 | 19 |
| [worker/src/nodes/parsers/txt\_parser.py](/worker/src/nodes/parsers/txt_parser.py) | Python | 53 | 4 | 16 | 73 |
| [worker/src/nodes/splitters/base\_splitter.py](/worker/src/nodes/splitters/base_splitter.py) | Python | 7 | 1 | 5 | 13 |
| [worker/src/nodes/splitters/token\_splitter.py](/worker/src/nodes/splitters/token_splitter.py) | Python | 50 | 7 | 14 | 71 |
| [worker/src/pipelines/ingestion.py](/worker/src/pipelines/ingestion.py) | Python | 63 | 22 | 17 | 102 |
| [worker/src/pipelines/qa.py](/worker/src/pipelines/qa.py) | Python | 53 | 6 | 14 | 73 |
| [worker/src/pipelines/retrieval.py](/worker/src/pipelines/retrieval.py) | Python | 83 | 19 | 22 | 124 |
| [worker/src/schemas/document.py](/worker/src/schemas/document.py) | Python | 22 | 0 | 7 | 29 |
| [worker/src/schemas/task.py](/worker/src/schemas/task.py) | Python | 7 | 0 | 3 | 10 |
| [worker/src/server.py](/worker/src/server.py) | Python | 81 | 17 | 17 | 115 |
| [worker/src/util/http.py](/worker/src/util/http.py) | Python | 17 | 8 | 6 | 31 |
| [worker/src/vector\_store/base\_store.py](/worker/src/vector_store/base_store.py) | Python | 8 | 1 | 5 | 14 |
| [worker/src/vector\_store/chroma\_store.py](/worker/src/vector_store/chroma_store.py) | Python | 74 | 13 | 18 | 105 |
| [worker/src/vector\_store/simple\_store.py](/worker/src/vector_store/simple_store.py) | Python | 74 | 10 | 22 | 106 |
| [worker/tests/mock\_openai\_server.py](/worker/tests/mock_openai_server.py) | Python | 46 | 8 | 15 | 69 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)