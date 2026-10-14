package service

import (
	"errors"
	"testing"
)

func TestTransferReservationAllowsOnlyOneActiveTask(t *testing.T) {
	service := &TransferService{}

	first, err := service.claimTransfer()
	if err != nil {
		t.Fatalf("claim first transfer: %v", err)
	}
	if _, err := service.claimTransfer(); !errors.Is(err, ErrTransferInProgress) {
		t.Fatalf("second claim error = %v; want ErrTransferInProgress", err)
	}

	service.bindTransfer(first, "task-1")
	service.releaseTransfer(first)
	if _, err := service.claimTransfer(); !errors.Is(err, ErrTransferInProgress) {
		t.Fatalf("releasing old reservation cleared the bound task: error = %v", err)
	}

	service.releaseTransfer("task-1")
	if _, err := service.claimTransfer(); err != nil {
		t.Fatalf("claim after release: %v", err)
	}
}
