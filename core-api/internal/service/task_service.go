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
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log, created_at, updated_at
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
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log, created_at, updated_at
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

// Retry resets a failed/completed task back to pending so it can be
// re-submitted to Worker (see task_handler.go's Retry).
func (s *TaskService) Retry(id string) error {
	return s.transition(id, models.TaskStatusPending, 0, "", "retry", "")
}

// ReconcileOrphaned fails every task still pending/processing, returning the
// tasks it touched so the caller can also fix up anything derived from task
// state (an in-flight ingest's book status — see grpcserver.ReportFail's
// matching Type == TaskTypeIngest guard).
//
// Worker runs a task in its own in-process thread with no persistence of its
// own (see docs/系统设计文档.md §3.x "Worker 只算、Core API 统一持久化") — it
// reports back over gRPC when done, but if either side restarts or Worker's
// process dies mid-task, that callback never arrives and the task would
// otherwise stay stuck at pending/processing forever with nothing to notice.
// Called both at Core API startup (main.go: any such task predates this
// process, so nothing is still tracking it — see docs/Todos.md) and by the
// Worker health-check loop (main.go's watchWorkerHealth) once Worker itself
// is found unreachable.
func (s *TaskService) ReconcileOrphaned(reason string) ([]models.Task, error) {
	rows, err := s.db.Query(
		`SELECT id, book_id, user_id, type, status, progress, error_msg, stages_log, created_at, updated_at
		 FROM tasks WHERE status IN (?, ?)`,
		models.TaskStatusPending, models.TaskStatusProcessing,
	)
	if err != nil {
		return nil, fmt.Errorf("query orphaned tasks: %w", err)
	}
	var orphaned []models.Task
	for rows.Next() {
		t, err := scanTaskRows(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		orphaned = append(orphaned, *t)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return nil, err
	}
	rows.Close() // must be closed before Fail() below issues its own queries on the same *sql.DB

	for _, t := range orphaned {
		if err := s.Fail(t.ID, reason); err != nil {
			return nil, fmt.Errorf("fail orphaned task %s: %w", t.ID, err)
		}
	}
	return orphaned, nil
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
		&t.StagesLog, &t.CreatedAt, &t.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, err
	}
	if err != nil {
		return nil, fmt.Errorf("scan task: %w", err)
	}
	return &t, nil
}
