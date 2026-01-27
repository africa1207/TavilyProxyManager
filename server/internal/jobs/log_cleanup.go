package jobs

import (
	"context"
	"log/slog"
	"sync/atomic"
	"time"

	"tavily-proxy/server/internal/services"
)

func StartLogCleanup(ctx context.Context, settings *services.SettingsService, logs *services.LogService, logger *slog.Logger) {
	var running atomic.Bool

	go func() {
		ticker := time.NewTicker(30 * time.Minute)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				if running.Load() {
					continue
				}

				retentionDays, err := settings.GetInt(ctx, services.SettingLogRetentionDays, 30)
				if err != nil {
					logger.Error("log-cleanup: failed to read retention setting", "err", err)
					continue
				}
				if retentionDays <= 0 {
					continue
				}

				lastRunAt, _ := settings.GetTime(ctx, services.SettingLogCleanupLastRunAt)
				if lastRunAt != nil && time.Since(*lastRunAt) < 24*time.Hour {
					continue
				}

				if !running.CompareAndSwap(false, true) {
					continue
				}

				go func(retention int) {
					defer running.Store(false)

					now := time.Now()
					_ = settings.SetTime(context.Background(), services.SettingLogCleanupLastRunAt, now)

					cutoff := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location()).AddDate(0, 0, -retention)

					runCtx, cancel := context.WithTimeout(ctx, 5*time.Minute)
					defer cancel()

					deleted, err := logs.DeleteOlderThan(runCtx, cutoff)
					if err != nil {
						_ = settings.Set(context.Background(), services.SettingLogCleanupLastError, err.Error())
						logger.Error("log-cleanup: delete failed", "err", err)
						return
					}

					_ = settings.Set(context.Background(), services.SettingLogCleanupLastError, "")
					logger.Info("log-cleanup: completed", "deleted", deleted, "cutoff", cutoff.Format(time.RFC3339))
				}(retentionDays)
			}
		}
	}()
}
