// Package dispatch enforces worker.max_concurrent_tasks on ingest tasks
// (import + rebuild) — the only task type this app calls "构建"/build in its
// own UI copy. Summarize tasks are intentionally out of scope: they're
// triggered one at a time already (per-book, from BookDetailView.vue), and
// unlike ingest they don't get piled up in bulk (multi-file upload,
// BulkRebuild) the way this was built to guard against.
//
// Core API owns the queue, not Worker — the `tasks` table (already
// persistent, already survives restarts) doubles as it: TaskService.CreateTask
// leaves a fresh task queued (dispatched_at NULL); Dispatcher.TryDispatch
// hands queued tasks to Worker one at a time up to the concurrency cap,
// called after every task creation and every terminal transition (a freed
// slot should be picked up immediately) plus once at startup and on every
// Worker health-check tick (see main.go) as a safety net. This keeps
// Worker itself exactly as simple as before (still just "run whatever
// TriggerIngest tells you to, right now" — see worker/src/server.py) and
// keeps the "Worker never touches Core API's database" boundary intact
// (see .claude/memory/mynexus_m2_decisions.md).
package dispatch

import (
	"log"
	"path/filepath"
	"sync"

	"mynexus/core-api/internal/coordinator"
	"mynexus/core-api/internal/models"
	"mynexus/core-api/internal/service"
)

type Dispatcher struct {
	tasks         *service.TaskService
	books         *service.BookService
	worker        *coordinator.WorkerClient
	maxConcurrent int

	// Serializes TryDispatch so two concurrent callers (e.g. a BulkRebuild
	// loop creating tasks while a completion callback fires from Worker at
	// the same time) can't both read "N free slots" and both act on it,
	// overshooting maxConcurrent. Core API is a single process (see
	// docs/系统设计文档.md's sqlite/small-scale positioning) so an in-process
	// mutex is sufficient — no cross-process coordination needed.
	mu sync.Mutex
}

func New(tasks *service.TaskService, books *service.BookService, worker *coordinator.WorkerClient, maxConcurrent int) *Dispatcher {
	if maxConcurrent < 1 {
		maxConcurrent = 1
	}
	return &Dispatcher{tasks: tasks, books: books, worker: worker, maxConcurrent: maxConcurrent}
}

// TryDispatch hands as many queued ingest tasks to Worker as the current
// concurrency cap allows, oldest-first. Safe to call any time, any number
// of times — a no-op once the cap is full or the queue is empty. Never
// returns an error: dispatch failures (Worker unreachable) are logged and
// leave the task queued for the next call to retry, same as any other
// best-effort background operation in this codebase.
func (d *Dispatcher) TryDispatch() {
	d.mu.Lock()
	defer d.mu.Unlock()

	for {
		running, err := d.tasks.CountDispatched(models.TaskTypeIngest)
		if err != nil {
			log.Printf("dispatch: count running ingest tasks: %v", err)
			return
		}
		if running >= d.maxConcurrent {
			return
		}

		task, err := d.tasks.NextQueued(models.TaskTypeIngest)
		if err != nil {
			log.Printf("dispatch: find next queued ingest task: %v", err)
			return
		}
		if task == nil {
			return // nothing waiting
		}

		if err := d.dispatchIngest(*task); err != nil {
			// Most likely Worker is unreachable — leave this (and whatever
			// else is queued) for the next TryDispatch call rather than
			// looping through the rest of the queue hitting the same
			// error. main.go's watchWorkerHealth ticks every 20s and calls
			// TryDispatch again regardless of connection state, so this
			// self-heals once Worker comes back with no manual retry
			// needed.
			log.Printf("dispatch: task %s still queued, could not reach worker: %v", task.ID, err)
			return
		}
	}
}

// dispatchIngest calls Worker first and only marks the task dispatched on
// success — if TriggerIngest fails, the task's dispatched_at stays NULL and
// it's simply retried by a later TryDispatch call, no rollback needed.
func (d *Dispatcher) dispatchIngest(task models.Task) error {
	book, err := d.books.GetBook(task.BookID)
	if err != nil {
		return err
	}
	if err := d.worker.TriggerIngest(coordinator.IngestRequest{
		TaskID: task.ID, BookID: task.BookID, FilePath: book.FilePath,
		OriginalFilename: filepath.Base(book.FilePath),
	}); err != nil {
		return err
	}
	return d.tasks.MarkDispatched(task.ID)
}
