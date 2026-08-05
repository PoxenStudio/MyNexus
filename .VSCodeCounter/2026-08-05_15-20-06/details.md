# Details

Date : 2026-08-05 15:20:06

Directory /Volumes/data/projects/poxenstudio/MyNexus/core-api

Total : 61 files,  5699 codes, 578 comments, 926 blanks, all 7203 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

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

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)