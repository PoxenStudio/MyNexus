# Diff Details

Date : 2026-08-05 15:20:06

Directory /Volumes/data/projects/poxenstudio/MyNexus/core-api

Total : 95 files,  3789 codes, 312 comments, 510 blanks, all 4611 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [core-api/Dockerfile](/core-api/Dockerfile) | Docker | 25 | 0 | 6 | 31 |
| [core-api/cmd/mynexus-api/main.go](/core-api/cmd/mynexus-api/main.go) | Go | 49 | 6 | 10 | 65 |
| [core-api/go.mod](/core-api/go.mod) | Go Module File | 50 | 0 | 4 | 54 |
| [core-api/go.sum](/core-api/go.sum) | Go Checksum File | 175 | 0 | 1 | 176 |
| [core-api/internal/api/dto/audit\_dto.go](/core-api/internal/api/dto/audit_dto.go) | Go | 23 | 0 | 5 | 28 |
| [core-api/internal/api/dto/book\_dto.go](/core-api/internal/api/dto/book_dto.go) | Go | 100 | 2 | 18 | 120 |
| [core-api/internal/api/dto/chat\_dto.go](/core-api/internal/api/dto/chat_dto.go) | Go | 60 | 5 | 12 | 77 |
| [core-api/internal/api/dto/search\_dto.go](/core-api/internal/api/dto/search_dto.go) | Go | 36 | 4 | 7 | 47 |
| [core-api/internal/api/dto/settings\_dto.go](/core-api/internal/api/dto/settings_dto.go) | Go | 11 | 4 | 3 | 18 |
| [core-api/internal/api/dto/task\_dto.go](/core-api/internal/api/dto/task_dto.go) | Go | 63 | 1 | 13 | 77 |
| [core-api/internal/api/dto/token\_dto.go](/core-api/internal/api/dto/token_dto.go) | Go | 28 | 1 | 7 | 36 |
| [core-api/internal/api/handler/audit\_handler.go](/core-api/internal/api/handler/audit_handler.go) | Go | 28 | 0 | 9 | 37 |
| [core-api/internal/api/handler/auth\_handler.go](/core-api/internal/api/handler/auth_handler.go) | Go | 176 | 15 | 29 | 220 |
| [core-api/internal/api/handler/book\_handler.go](/core-api/internal/api/handler/book_handler.go) | Go | 233 | 13 | 40 | 286 |
| [core-api/internal/api/handler/chat\_handler.go](/core-api/internal/api/handler/chat_handler.go) | Go | 142 | 10 | 21 | 173 |
| [core-api/internal/api/handler/search\_handler.go](/core-api/internal/api/handler/search_handler.go) | Go | 53 | 0 | 11 | 64 |
| [core-api/internal/api/handler/system\_handler.go](/core-api/internal/api/handler/system_handler.go) | Go | 109 | 21 | 22 | 152 |
| [core-api/internal/api/handler/task\_handler.go](/core-api/internal/api/handler/task_handler.go) | Go | 77 | 2 | 14 | 93 |
| [core-api/internal/api/handler/token\_handler.go](/core-api/internal/api/handler/token_handler.go) | Go | 50 | 0 | 10 | 60 |
| [core-api/internal/api/middleware/auth.go](/core-api/internal/api/middleware/auth.go) | Go | 47 | 14 | 8 | 69 |
| [core-api/internal/api/middleware/cors.go](/core-api/internal/api/middleware/cors.go) | Go | 41 | 8 | 7 | 56 |
| [core-api/internal/api/middleware/ratelimit.go](/core-api/internal/api/middleware/ratelimit.go) | Go | 42 | 5 | 9 | 56 |
| [core-api/internal/api/router.go](/core-api/internal/api/router.go) | Go | 79 | 8 | 18 | 105 |
| [core-api/internal/auth/api\_token.go](/core-api/internal/auth/api_token.go) | Go | 19 | 3 | 4 | 26 |
| [core-api/internal/auth/password.go](/core-api/internal/auth/password.go) | Go | 9 | 0 | 4 | 13 |
| [core-api/internal/auth/session.go](/core-api/internal/auth/session.go) | Go | 53 | 9 | 12 | 74 |
| [core-api/internal/config/config.go](/core-api/internal/config/config.go) | Go | 169 | 56 | 25 | 250 |
| [core-api/internal/coordinator/worker\_client.go](/core-api/internal/coordinator/worker_client.go) | Go | 166 | 39 | 31 | 236 |
| [core-api/internal/grpcapi/mynexuspb/mynexus.pb.go](/core-api/internal/grpcapi/mynexuspb/mynexus.pb.go) | Go | 1,538 | 51 | 247 | 1,836 |
| [core-api/internal/grpcapi/mynexuspb/mynexus\_grpc.pb.go](/core-api/internal/grpcapi/mynexuspb/mynexus_grpc.pb.go) | Go | 506 | 138 | 51 | 695 |
| [core-api/internal/grpcserver/server.go](/core-api/internal/grpcserver/server.go) | Go | 147 | 23 | 26 | 196 |
| [core-api/internal/models/admin\_user.go](/core-api/internal/models/admin_user.go) | Go | 9 | 2 | 2 | 13 |
| [core-api/internal/models/api\_token.go](/core-api/internal/models/api_token.go) | Go | 12 | 0 | 2 | 14 |
| [core-api/internal/models/audit\_log.go](/core-api/internal/models/audit_log.go) | Go | 10 | 0 | 2 | 12 |
| [core-api/internal/models/book.go](/core-api/internal/models/book.go) | Go | 29 | 4 | 4 | 37 |
| [core-api/internal/models/chapter.go](/core-api/internal/models/chapter.go) | Go | 10 | 0 | 2 | 12 |
| [core-api/internal/models/chat\_session.go](/core-api/internal/models/chat_session.go) | Go | 21 | 0 | 4 | 25 |
| [core-api/internal/models/chunk.go](/core-api/internal/models/chunk.go) | Go | 11 | 0 | 2 | 13 |
| [core-api/internal/models/task.go](/core-api/internal/models/task.go) | Go | 29 | 3 | 5 | 37 |
| [core-api/internal/service/admin\_user\_service.go](/core-api/internal/service/admin_user_service.go) | Go | 96 | 10 | 15 | 121 |
| [core-api/internal/service/audit\_service.go](/core-api/internal/service/audit_service.go) | Go | 55 | 3 | 11 | 69 |
| [core-api/internal/service/book\_service.go](/core-api/internal/service/book_service.go) | Go | 345 | 31 | 54 | 430 |
| [core-api/internal/service/chat\_service.go](/core-api/internal/service/chat_service.go) | Go | 93 | 0 | 15 | 108 |
| [core-api/internal/service/task\_service.go](/core-api/internal/service/task_service.go) | Go | 133 | 6 | 23 | 162 |
| [core-api/internal/service/token\_service.go](/core-api/internal/service/token_service.go) | Go | 81 | 5 | 13 | 99 |
| [core-api/internal/storage/database.go](/core-api/internal/storage/database.go) | Go | 7 | 4 | 3 | 14 |
| [core-api/internal/storage/migrator.go](/core-api/internal/storage/migrator.go) | Go | 82 | 15 | 11 | 108 |
| [core-api/internal/storage/postgres/migrations/0001\_init.sql](/core-api/internal/storage/postgres/migrations/0001_init.sql) | MS SQL | 81 | 3 | 8 | 92 |
| [core-api/internal/storage/postgres/migrations/0002\_admin\_users.sql](/core-api/internal/storage/postgres/migrations/0002_admin_users.sql) | MS SQL | 7 | 1 | 2 | 10 |
| [core-api/internal/storage/postgres/migrations/0003\_admin\_audit\_log.sql](/core-api/internal/storage/postgres/migrations/0003_admin_audit_log.sql) | MS SQL | 10 | 1 | 2 | 13 |
| [core-api/internal/storage/postgres/migrations/0004\_chunk\_keyword\_search.sql](/core-api/internal/storage/postgres/migrations/0004_chunk_keyword_search.sql) | MS SQL | 3 | 10 | 3 | 16 |
| [core-api/internal/storage/postgres/migrations/0005\_admin\_avatar.sql](/core-api/internal/storage/postgres/migrations/0005_admin_avatar.sql) | MS SQL | 1 | 1 | 2 | 4 |
| [core-api/internal/storage/postgres/migrations/0006\_book\_summary.sql](/core-api/internal/storage/postgres/migrations/0006_book_summary.sql) | MS SQL | 1 | 1 | 2 | 4 |
| [core-api/internal/storage/postgres/postgres.go](/core-api/internal/storage/postgres/postgres.go) | Go | 33 | 5 | 10 | 48 |
| [core-api/internal/storage/postgres/qmark\_driver.go](/core-api/internal/storage/postgres/qmark_driver.go) | Go | 93 | 7 | 17 | 117 |
| [core-api/internal/storage/sqlite/migrations/0001\_init.sql](/core-api/internal/storage/sqlite/migrations/0001_init.sql) | MS SQL | 81 | 1 | 8 | 90 |
| [core-api/internal/storage/sqlite/migrations/0002\_admin\_users.sql](/core-api/internal/storage/sqlite/migrations/0002_admin_users.sql) | MS SQL | 7 | 4 | 2 | 13 |
| [core-api/internal/storage/sqlite/migrations/0003\_admin\_audit\_log.sql](/core-api/internal/storage/sqlite/migrations/0003_admin_audit_log.sql) | MS SQL | 10 | 3 | 2 | 15 |
| [core-api/internal/storage/sqlite/migrations/0004\_admin\_avatar.sql](/core-api/internal/storage/sqlite/migrations/0004_admin_avatar.sql) | MS SQL | 1 | 3 | 2 | 6 |
| [core-api/internal/storage/sqlite/migrations/0005\_book\_summary.sql](/core-api/internal/storage/sqlite/migrations/0005_book_summary.sql) | MS SQL | 1 | 4 | 2 | 7 |
| [core-api/internal/storage/sqlite/sqlite.go](/core-api/internal/storage/sqlite/sqlite.go) | Go | 43 | 13 | 12 | 68 |
| [worker/Dockerfile](/worker/Dockerfile) | Docker | -20 | 0 | -5 | -25 |
| [worker/requirements.txt](/worker/requirements.txt) | pip requirements | -8 | 0 | -1 | -9 |
| [worker/src/config.py](/worker/src/config.py) | Python | -85 | -17 | -29 | -131 |
| [worker/src/grpc\_client.py](/worker/src/grpc_client.py) | Python | -46 | -14 | -10 | -70 |
| [worker/src/mynexus\_pb2.py](/worker/src/mynexus_pb2.py) | Python | -77 | -8 | -7 | -92 |
| [worker/src/mynexus\_pb2.pyi](/worker/src/mynexus_pb2.pyi) | Python | -189 | 0 | -22 | -211 |
| [worker/src/mynexus\_pb2\_grpc.py](/worker/src/mynexus_pb2_grpc.py) | Python | -521 | -81 | -47 | -649 |
| [worker/src/nodes/base.py](/worker/src/nodes/base.py) | Python | -10 | -1 | -5 | -16 |
| [worker/src/nodes/cleaners/base\_cleaner.py](/worker/src/nodes/cleaners/base_cleaner.py) | Python | -6 | -1 | -5 | -12 |
| [worker/src/nodes/cleaners/whitespace\_cleaner.py](/worker/src/nodes/cleaners/whitespace_cleaner.py) | Python | -20 | -2 | -11 | -33 |
| [worker/src/nodes/embedders/base\_embedder.py](/worker/src/nodes/embedders/base_embedder.py) | Python | -9 | -1 | -6 | -16 |
| [worker/src/nodes/embedders/ollama\_embedder.py](/worker/src/nodes/embedders/ollama_embedder.py) | Python | -40 | -3 | -12 | -55 |
| [worker/src/nodes/embedders/openai\_embedder.py](/worker/src/nodes/embedders/openai_embedder.py) | Python | -46 | -5 | -14 | -65 |
| [worker/src/nodes/factory.py](/worker/src/nodes/factory.py) | Python | -24 | 0 | -7 | -31 |
| [worker/src/nodes/llm/base\_llm.py](/worker/src/nodes/llm/base_llm.py) | Python | -7 | -1 | -5 | -13 |
| [worker/src/nodes/llm/ollama\_llm.py](/worker/src/nodes/llm/ollama_llm.py) | Python | -42 | -3 | -11 | -56 |
| [worker/src/nodes/llm/openai\_llm.py](/worker/src/nodes/llm/openai_llm.py) | Python | -50 | -4 | -11 | -65 |
| [worker/src/nodes/parsers/base\_parser.py](/worker/src/nodes/parsers/base_parser.py) | Python | -11 | -6 | -6 | -23 |
| [worker/src/nodes/parsers/epub\_parser.py](/worker/src/nodes/parsers/epub_parser.py) | Python | -49 | -2 | -15 | -66 |
| [worker/src/nodes/parsers/registry.py](/worker/src/nodes/parsers/registry.py) | Python | -12 | -1 | -6 | -19 |
| [worker/src/nodes/parsers/txt\_parser.py](/worker/src/nodes/parsers/txt_parser.py) | Python | -53 | -4 | -16 | -73 |
| [worker/src/nodes/splitters/base\_splitter.py](/worker/src/nodes/splitters/base_splitter.py) | Python | -7 | -1 | -5 | -13 |
| [worker/src/nodes/splitters/token\_splitter.py](/worker/src/nodes/splitters/token_splitter.py) | Python | -50 | -7 | -14 | -71 |
| [worker/src/pipelines/ingestion.py](/worker/src/pipelines/ingestion.py) | Python | -63 | -22 | -17 | -102 |
| [worker/src/pipelines/qa.py](/worker/src/pipelines/qa.py) | Python | -53 | -6 | -14 | -73 |
| [worker/src/pipelines/retrieval.py](/worker/src/pipelines/retrieval.py) | Python | -83 | -19 | -22 | -124 |
| [worker/src/schemas/document.py](/worker/src/schemas/document.py) | Python | -22 | 0 | -7 | -29 |
| [worker/src/schemas/task.py](/worker/src/schemas/task.py) | Python | -7 | 0 | -3 | -10 |
| [worker/src/server.py](/worker/src/server.py) | Python | -81 | -17 | -17 | -115 |
| [worker/src/util/http.py](/worker/src/util/http.py) | Python | -17 | -8 | -6 | -31 |
| [worker/src/vector\_store/base\_store.py](/worker/src/vector_store/base_store.py) | Python | -8 | -1 | -5 | -14 |
| [worker/src/vector\_store/chroma\_store.py](/worker/src/vector_store/chroma_store.py) | Python | -74 | -13 | -18 | -105 |
| [worker/src/vector\_store/simple\_store.py](/worker/src/vector_store/simple_store.py) | Python | -74 | -10 | -22 | -106 |
| [worker/tests/mock\_openai\_server.py](/worker/tests/mock_openai_server.py) | Python | -46 | -8 | -15 | -69 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details