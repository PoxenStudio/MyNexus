package service

import (
	"database/sql"
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

func (s *TaskService) ListTasks(page, size int, status string) ([]models.Task, int64, error) {
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

func (s *TaskService) UpdateProgress(id string, progress int) error {
	_, err := s.db.Exec(
		`UPDATE tasks SET status = ?, progress = ?, updated_at = ? WHERE id = ?`,
		models.TaskStatusProcessing, progress, time.Now().UTC().Format(time.RFC3339), id,
	)
	return err
}

func (s *TaskService) Complete(id string) error {
	return s.updateStatus(id, models.TaskStatusCompleted, 100, "")
}

func (s *TaskService) Fail(id, errMsg string) error {
	return s.updateStatus(id, models.TaskStatusFailed, 0, errMsg)
}

func (s *TaskService) updateStatus(id, status string, progress int, errMsg string) error {
	_, err := s.db.Exec(
		`UPDATE tasks SET status = ?, progress = ?, error_msg = ?, updated_at = ? WHERE id = ?`,
		status, progress, errMsg, time.Now().UTC().Format(time.RFC3339), id,
	)
	return err
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
