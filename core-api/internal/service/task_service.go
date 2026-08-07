package service

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"mynexus/core-api/internal/models"
)

type TaskService struct {
	db *sql.DB
}

func NewTaskService(db *sql.DB) *TaskService {
	return &TaskService{db: db}
}

func (s *TaskService) CreateTask(bookID, userID, taskType string) (*models.Task, error) {
	now := time.Now().UTC().Format(time.RFC3339)
	task := &models.Task{
		ID:        uuid.NewString(),
		BookID:    bookID,
		UserID:    userID,
		Type:      taskType,
		Status:    models.TaskStatusPending,
		StagesLog: "[]",
		CreatedAt: now,
		UpdatedAt: now,
	}
	_, err := s.db.Exec(
		`INSERT INTO tasks (id, book_id, user_id, type, status, progress, error_msg, stages_log, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, 0, '', ?, ?, ?)`,
		task.ID, task.BookID, task.UserID, task.Type, task.Status, task.StagesLog, task.CreatedAt, task.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("insert task: %w", err)
	}
	return task, nil
}

func (s *TaskService) GetTask(id string) (*models.Task, error) {
	row := s.db.QueryRow(
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log,
			COALESCE(dispatched_at, ''), created_at, updated_at
		 FROM tasks WHERE id = ?`, id)
	return scanTask(row)
}

func (s *TaskService) ListTasks(page, size int, status, bookID string) ([]models.Task, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 || size > 200 {
		size = 20
	}

	where := "WHERE 1=1"
	args := []any{}
	if status != "" {
		where += " AND status = ?"
		args = append(args, status)
	}
	if bookID != "" {
		where += " AND book_id = ?"
		args = append(args, bookID)
	}

	var total int64
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM tasks `+where, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count tasks: %w", err)
	}

	listArgs := append(append([]any{}, args...), size, (page-1)*size)
	rows, err := s.db.Query(
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log,
			COALESCE(dispatched_at, ''), created_at, updated_at
		 FROM tasks `+where+` ORDER BY created_at DESC LIMIT ? OFFSET ?`, listArgs...)
	if err != nil {
		return nil, 0, fmt.Errorf("list tasks: %w", err)
	}
	defer rows.Close()

	var tasks []models.Task
	for rows.Next() {
		t, err := scanTaskRows(rows)
		if err != nil {
			return nil, 0, err
		}
		tasks = append(tasks, *t)
	}
	return tasks, total, rows.Err()
}

// Retry resets a failed/completed task back to pending — and, same as a
// freshly created task, un-dispatched — so it goes through
// internal/dispatch.Dispatcher's queue again instead of bypassing the
// worker.max_concurrent_tasks cap (see task_handler.go's Retry).
func (s *TaskService) Retry(id string) error {
	if err := s.transition(id, models.TaskStatusPending, 0, "", "retry", ""); err != nil {
		return err
	}
	_, err := s.db.Exec(`UPDATE tasks SET dispatched_at = NULL WHERE id = ?`, id)
	return err
}

// MarkDispatched records that id has actually been handed to Worker —
// called by internal/dispatch.Dispatcher right after a successful
// TriggerIngest, never before (a failed gRPC call leaves the task queued,
// safe to retry — see Dispatcher.dispatchIngest).
func (s *TaskService) MarkDispatched(id string) error {
	_, err := s.db.Exec(`UPDATE tasks SET dispatched_at = ? WHERE id = ?`, time.Now().UTC().Format(time.RFC3339), id)
	return err
}

// CountDispatched returns how many taskType tasks currently count against
// worker.max_concurrent_tasks: dispatched (handed to Worker) but not yet
// terminal. Used by Dispatcher.TryDispatch to decide whether there's a free
// slot before pulling the next queued task.
func (s *TaskService) CountDispatched(taskType string) (int, error) {
	var n int
	err := s.db.QueryRow(
		`SELECT COUNT(*) FROM tasks WHERE type = ? AND dispatched_at IS NOT NULL AND status IN (?, ?)`,
		taskType, models.TaskStatusPending, models.TaskStatusProcessing,
	).Scan(&n)
	return n, err
}

// NextQueued returns the oldest not-yet-dispatched taskType task (nil, nil
// if none), for Dispatcher.TryDispatch to hand to Worker next once a slot
// frees up. Oldest-first so a big batch (e.g. BulkRebuild, or several files
// uploaded back to back) is processed in the order it was submitted.
func (s *TaskService) NextQueued(taskType string) (*models.Task, error) {
	row := s.db.QueryRow(
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log,
			COALESCE(dispatched_at, ''), created_at, updated_at
		 FROM tasks WHERE type = ? AND status = ? AND dispatched_at IS NULL
		 ORDER BY created_at ASC LIMIT 1`,
		taskType, models.TaskStatusPending,
	)
	t, err := scanTaskRows(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return t, err
}

// RequeueOrphanedIngest resets every ingest task still pending/processing
// back to queued (status=pending, dispatched_at=NULL) — the caller
// (main.go) then kicks internal/dispatch.Dispatcher.TryDispatch so they're
// naturally resubmitted to Worker, respecting worker.max_concurrent_tasks,
// instead of requiring a manual retry from the Tasks admin page. Returns
// the tasks it touched so the caller can also reset each one's book status
// back to "pending" (it was "processing", which is no longer true — nothing
// is actually running on it right now).
//
// Scoped to ingest only — summarize orphans still go through
// FailOrphanedSummarize below, since only ingest tasks are dispatcher-
// managed (see internal/dispatch.Dispatcher's doc comment for why).
//
// Worker runs a task in its own in-process thread with no persistence of its
// own (see docs/系统设计文档.md §3.x "Worker 只算、Core API 统一持久化") — it
// reports back over gRPC when done, but if either side restarts or Worker's
// process dies mid-task, that callback never arrives and the task would
// otherwise stay stuck at pending/processing forever with nothing to notice.
// Re-running an ingest task from scratch is safe/idempotent —
// SaveChapters/SaveChunks replace wholesale and vector_store.delete_by_book
// runs before re-upserting (see worker/src/pipelines/ingestion.py). Called
// both at Core API startup (main.go: any such task predates this process,
// so nothing is still tracking it — see docs/Todos.md) and by the Worker
// health-check loop (main.go's watchWorkerHealth) once Worker itself is
// found unreachable.
func (s *TaskService) RequeueOrphanedIngest() ([]models.Task, error) {
	orphaned, err := s.queryOrphaned(models.TaskTypeIngest)
	if err != nil {
		return nil, err
	}
	for _, t := range orphaned {
		if err := s.requeue(t.ID); err != nil {
			return nil, fmt.Errorf("requeue orphaned task %s: %w", t.ID, err)
		}
	}
	return orphaned, nil
}

// FailOrphanedSummarize is RequeueOrphanedIngest's counterpart for
// summarize tasks, which aren't dispatcher-managed (no concurrency cap to
// enforce there) — so there's no queue to naturally resubmit them from,
// unlike ingest. Falls back to the older "just fail it, surface it on the
// Tasks admin page for a manual Retry" behavior instead of leaving it stuck
// at pending/processing forever with nothing to notice or resume it.
func (s *TaskService) FailOrphanedSummarize(reason string) ([]models.Task, error) {
	orphaned, err := s.queryOrphaned(models.TaskTypeSummarize)
	if err != nil {
		return nil, err
	}
	for _, t := range orphaned {
		if err := s.Fail(t.ID, reason); err != nil {
			return nil, fmt.Errorf("fail orphaned task %s: %w", t.ID, err)
		}
	}
	return orphaned, nil
}

func (s *TaskService) queryOrphaned(taskType string) ([]models.Task, error) {
	rows, err := s.db.Query(
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log,
			COALESCE(dispatched_at, ''), created_at, updated_at
		 FROM tasks WHERE type = ? AND status IN (?, ?)`,
		taskType, models.TaskStatusPending, models.TaskStatusProcessing,
	)
	if err != nil {
		return nil, fmt.Errorf("query orphaned %s tasks: %w", taskType, err)
	}
	defer rows.Close()

	var orphaned []models.Task
	for rows.Next() {
		t, err := scanTaskRows(rows)
		if err != nil {
			return nil, err
		}
		orphaned = append(orphaned, *t)
	}
	return orphaned, rows.Err()
}

func (s *TaskService) requeue(id string) error {
	stagesLog, err := s.appendStageLog(id, "requeued", "服务重启或连接中断，任务已重新排队等待处理", 0)
	if err != nil {
		return err
	}
	_, err = s.db.Exec(
		`UPDATE tasks SET status = ?, dispatched_at = NULL, stages_log = ?, updated_at = ? WHERE id = ?`,
		models.TaskStatusPending, stagesLog, time.Now().UTC().Format(time.RFC3339), id,
	)
	return err
}

func (s *TaskService) UpdateProgress(id string, progress int, stage, message string) error {
	return s.transition(id, models.TaskStatusProcessing, progress, "", stage, message)
}

func (s *TaskService) Complete(id string) error {
	return s.transition(id, models.TaskStatusCompleted, 100, "", "completed", "")
}

func (s *TaskService) Fail(id, errMsg string) error {
	return s.transition(id, models.TaskStatusFailed, 0, errMsg, "failed", errMsg)
}

// transition updates status/progress/error_msg and appends a structured entry
// to stages_log in one go, so every state change Core API records for a task
// (progress ticks from Worker, completion, failure, manual retry) leaves a
// timestamped trail — not just the latest flat error_msg.
func (s *TaskService) transition(id, status string, progress int, errMsg, stage, stageMessage string) error {
	stagesLog, err := s.appendStageLog(id, stage, stageMessage, progress)
	if err != nil {
		return err
	}
	_, err = s.db.Exec(
		`UPDATE tasks SET status = ?, progress = ?, error_msg = ?, stages_log = ?, updated_at = ? WHERE id = ?`,
		status, progress, errMsg, stagesLog, time.Now().UTC().Format(time.RFC3339), id,
	)
	return err
}

func (s *TaskService) appendStageLog(id, stage, message string, progress int) (string, error) {
	var current string
	if err := s.db.QueryRow(`SELECT stages_log FROM tasks WHERE id = ?`, id).Scan(&current); err != nil {
		return "", fmt.Errorf("read stages_log: %w", err)
	}

	var entries []models.StageLogEntry
	_ = json.Unmarshal([]byte(current), &entries)
	entries = append(entries, models.StageLogEntry{
		Stage: stage, Message: message, Progress: progress,
		At: time.Now().UTC().Format(time.RFC3339),
	})

	b, err := json.Marshal(entries)
	if err != nil {
		return "", fmt.Errorf("marshal stages_log: %w", err)
	}
	return string(b), nil
}

func scanTask(row rowScanner) (*models.Task, error) {
	return scanTaskRows(row)
}

func scanTaskRows(row rowScanner) (*models.Task, error) {
	var t models.Task
	err := row.Scan(&t.ID, &t.BookID, &t.UserID, &t.Type, &t.Status, &t.Progress, &t.ErrorMsg,
		&t.StagesLog, &t.DispatchedAt, &t.CreatedAt, &t.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, err
	}
	if err != nil {
		return nil, fmt.Errorf("scan task: %w", err)
	}
	return &t, nil
}
