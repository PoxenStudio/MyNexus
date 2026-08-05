# Diff Details

Date : 2026-08-05 15:19:57

Directory /Volumes/data/projects/poxenstudio/MyNexus/worker

Total : 80 files,  -3809 codes, 221 comments, 121 blanks, all -3467 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [web-ui/Dockerfile](/web-ui/Dockerfile) | Docker | -21 | 0 | -6 | -27 |
| [web-ui/README.md](/web-ui/README.md) | Markdown | -3 | 0 | -3 | -6 |
| [web-ui/index.html](/web-ui/index.html) | HTML | -13 | 0 | -1 | -14 |
| [web-ui/package-lock.json](/web-ui/package-lock.json) | JSON | -2,138 | 0 | -1 | -2,139 |
| [web-ui/package.json](/web-ui/package.json) | JSON | -26 | 0 | -1 | -27 |
| [web-ui/public/favicon.svg](/web-ui/public/favicon.svg) | XML | -1 | 0 | 0 | -1 |
| [web-ui/public/icons.svg](/web-ui/public/icons.svg) | XML | -24 | 0 | -1 | -25 |
| [web-ui/src/App.vue](/web-ui/src/App.vue) | vue | -18 | 0 | -4 | -22 |
| [web-ui/src/api/audit.ts](/web-ui/src/api/audit.ts) | TypeScript | -20 | 0 | -4 | -24 |
| [web-ui/src/api/auth.ts](/web-ui/src/api/auth.ts) | TypeScript | -23 | 0 | -6 | -29 |
| [web-ui/src/api/books.ts](/web-ui/src/api/books.ts) | TypeScript | -66 | 0 | -13 | -79 |
| [web-ui/src/api/chat.ts](/web-ui/src/api/chat.ts) | TypeScript | -67 | -4 | -11 | -82 |
| [web-ui/src/api/client.ts](/web-ui/src/api/client.ts) | TypeScript | -5 | -2 | -2 | -9 |
| [web-ui/src/api/system.ts](/web-ui/src/api/system.ts) | TypeScript | -77 | -6 | -11 | -94 |
| [web-ui/src/api/tasks.ts](/web-ui/src/api/tasks.ts) | TypeScript | -32 | 0 | -6 | -38 |
| [web-ui/src/api/tokens.ts](/web-ui/src/api/tokens.ts) | TypeScript | -20 | 0 | -5 | -25 |
| [web-ui/src/assets/vite.svg](/web-ui/src/assets/vite.svg) | XML | -1 | 0 | -1 | -2 |
| [web-ui/src/components/AppDialog.vue](/web-ui/src/components/AppDialog.vue) | vue | -71 | 0 | -4 | -75 |
| [web-ui/src/components/AppIcon.vue](/web-ui/src/components/AppIcon.vue) | vue | -45 | 0 | -4 | -49 |
| [web-ui/src/components/AppLayout.vue](/web-ui/src/components/AppLayout.vue) | vue | -420 | 0 | -31 | -451 |
| [web-ui/src/components/StatCard.vue](/web-ui/src/components/StatCard.vue) | vue | -26 | 0 | -3 | -29 |
| [web-ui/src/components/charts/BarChart.vue](/web-ui/src/components/charts/BarChart.vue) | vue | -64 | 0 | -6 | -70 |
| [web-ui/src/i18n/en-US.json](/web-ui/src/i18n/en-US.json) | JSON | -175 | 0 | -1 | -176 |
| [web-ui/src/i18n/index.ts](/web-ui/src/i18n/index.ts) | TypeScript | -34 | -3 | -7 | -44 |
| [web-ui/src/i18n/zh-CN.json](/web-ui/src/i18n/zh-CN.json) | JSON | -175 | 0 | -1 | -176 |
| [web-ui/src/i18n/zh-TW.json](/web-ui/src/i18n/zh-TW.json) | JSON | -175 | 0 | -1 | -176 |
| [web-ui/src/main.ts](/web-ui/src/main.ts) | TypeScript | -11 | -2 | -4 | -17 |
| [web-ui/src/router/index.ts](/web-ui/src/router/index.ts) | TypeScript | -78 | -3 | -6 | -87 |
| [web-ui/src/stores/appConfig.ts](/web-ui/src/stores/appConfig.ts) | TypeScript | -18 | 0 | -2 | -20 |
| [web-ui/src/stores/auth.ts](/web-ui/src/stores/auth.ts) | TypeScript | -42 | -7 | -2 | -51 |
| [web-ui/src/stores/theme.ts](/web-ui/src/stores/theme.ts) | TypeScript | -29 | -4 | -6 | -39 |
| [web-ui/src/style.css](/web-ui/src/style.css) | PostCSS | -131 | -11 | -18 | -160 |
| [web-ui/src/views/ChatView.vue](/web-ui/src/views/ChatView.vue) | vue | -202 | 0 | -14 | -216 |
| [web-ui/src/views/LoginView.vue](/web-ui/src/views/LoginView.vue) | vue | -114 | 0 | -6 | -120 |
| [web-ui/src/views/admin/AdminAccountView.vue](/web-ui/src/views/admin/AdminAccountView.vue) | vue | -235 | 0 | -14 | -249 |
| [web-ui/src/views/admin/AuditLogView.vue](/web-ui/src/views/admin/AuditLogView.vue) | vue | -71 | 0 | -7 | -78 |
| [web-ui/src/views/admin/BookDetailView.vue](/web-ui/src/views/admin/BookDetailView.vue) | vue | -65 | 0 | -8 | -73 |
| [web-ui/src/views/admin/BooksListView.vue](/web-ui/src/views/admin/BooksListView.vue) | vue | -271 | 0 | -20 | -291 |
| [web-ui/src/views/admin/DashboardView.vue](/web-ui/src/views/admin/DashboardView.vue) | vue | -72 | 0 | -10 | -82 |
| [web-ui/src/views/admin/SystemConfigView.vue](/web-ui/src/views/admin/SystemConfigView.vue) | vue | -278 | 0 | -17 | -295 |
| [web-ui/src/views/admin/TasksView.vue](/web-ui/src/views/admin/TasksView.vue) | vue | -174 | 0 | -9 | -183 |
| [web-ui/src/views/admin/TokensView.vue](/web-ui/src/views/admin/TokensView.vue) | vue | -138 | 0 | -10 | -148 |
| [web-ui/tsconfig.app.json](/web-ui/tsconfig.app.json) | JSON | -13 | -1 | -2 | -16 |
| [web-ui/tsconfig.json](/web-ui/tsconfig.json) | JSON with Comments | -7 | 0 | -1 | -8 |
| [web-ui/tsconfig.node.json](/web-ui/tsconfig.node.json) | JSON | -19 | -2 | -3 | -24 |
| [web-ui/vite.config.ts](/web-ui/vite.config.ts) | TypeScript | -11 | 0 | -2 | -13 |
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

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details