package postgres

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"strings"

	"github.com/jackc/pgx/v5/stdlib"
)

// The service layer writes plain SQLite-style "?" placeholders (shared with the
// sqlite backend, see storage/sqlite). Postgres wants "$1, $2, ...". Rather than
// forking every query in internal/service for two placeholder styles, register a
// driver that rewrites "?" -> "$N" transparently around pgx's stdlib driver — the
// service layer stays backend-agnostic and only ever sees *sql.DB.
const driverName = "postgres-qmark"

func init() {
	sql.Register(driverName, &qmarkDriver{inner: stdlib.GetDefaultDriver()})
}

func rebind(query string) string {
	if !strings.Contains(query, "?") {
		return query
	}
	var b strings.Builder
	b.Grow(len(query) + 8)
	n := 0
	for _, r := range query {
		if r == '?' {
			n++
			b.WriteByte('$')
			b.WriteString(itoa(n))
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

type qmarkDriver struct{ inner driver.Driver }

func (d *qmarkDriver) Open(name string) (driver.Conn, error) {
	c, err := d.inner.Open(name)
	if err != nil {
		return nil, err
	}
	return &qmarkConn{Conn: c}, nil
}

// qmarkConn wraps a pgx stdlib connection, rewriting "?" placeholders to "$N"
// before delegating every query/exec/prepare path to the underlying connection.
type qmarkConn struct {
	driver.Conn
}

func (c *qmarkConn) Prepare(query string) (driver.Stmt, error) {
	return c.Conn.Prepare(rebind(query))
}

func (c *qmarkConn) PrepareContext(ctx context.Context, query string) (driver.Stmt, error) {
	if pc, ok := c.Conn.(driver.ConnPrepareContext); ok {
		return pc.PrepareContext(ctx, rebind(query))
	}
	return c.Prepare(query)
}

func (c *qmarkConn) ExecContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Result, error) {
	if ec, ok := c.Conn.(driver.ExecerContext); ok {
		return ec.ExecContext(ctx, rebind(query), args)
	}
	return nil, driver.ErrSkip
}

func (c *qmarkConn) QueryContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	if qc, ok := c.Conn.(driver.QueryerContext); ok {
		return qc.QueryContext(ctx, rebind(query), args)
	}
	return nil, driver.ErrSkip
}

func (c *qmarkConn) BeginTx(ctx context.Context, opts driver.TxOptions) (driver.Tx, error) {
	if bt, ok := c.Conn.(driver.ConnBeginTx); ok {
		return bt.BeginTx(ctx, opts)
	}
	return c.Conn.Begin()
}

func (c *qmarkConn) Ping(ctx context.Context) error {
	if p, ok := c.Conn.(driver.Pinger); ok {
		return p.Ping(ctx)
	}
	return nil
}

func (c *qmarkConn) CheckNamedValue(nv *driver.NamedValue) error {
	if chk, ok := c.Conn.(driver.NamedValueChecker); ok {
		return chk.CheckNamedValue(nv)
	}
	return driver.ErrSkip
}
