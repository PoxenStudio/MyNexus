package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/service"
)

type TaskHandler struct {
	tasks *service.TaskService
}

func NewTaskHandler(tasks *service.TaskService) *TaskHandler {
	return &TaskHandler{tasks: tasks}
}

func (h *TaskHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	size, _ := strconv.Atoi(c.DefaultQuery("size", "20"))
	status := c.Query("status")

	tasks, total, err := h.tasks.ListTasks(page, size, status)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	items := make([]dto.TaskResponse, 0, len(tasks))
	for _, t := range tasks {
		items = append(items, dto.NewTaskResponse(t))
	}
	c.JSON(http.StatusOK, dto.TaskListResponse{Items: items, Total: total, Page: page, Size: size})
}

func (h *TaskHandler) Get(c *gin.Context) {
	id := c.Param("id")
	task, err := h.tasks.GetTask(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	c.JSON(http.StatusOK, dto.NewTaskResponse(*task))
}
