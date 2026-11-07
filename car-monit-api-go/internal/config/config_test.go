package config

// 配置加载与新增开关的回归护栏（报告 01 Q7 / 报告 02 P0-3/P0-5/P0-7/P1-8）。

import (
	"path/filepath"
	"testing"
	"time"
)

// TestLoadExampleConfig 保证仓库里的配置模板能被真实解析并通过校验，
// 同时确认新增开关的默认值与文档一致。
func TestLoadExampleConfig(t *testing.T) {
	path := filepath.Join("..", "..", "configs", "config.example.yaml")
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("加载 config.example.yaml 失败: %v", err)
	}

	if cfg.Server.PprofEnabled {
		t.Error("pprof-enabled 默认必须为 false（P0-5）")
	}
	if !cfg.Server.MetricsEnabled {
		t.Error("metrics-enabled 默认必须为 true（P0-7）")
	}
	if cfg.Server.ConsumerRequiredForReady {
		t.Error("consumer-required-for-ready 默认必须为 false（保持 Java 侧 MQ 非强依赖语义）")
	}
	if cfg.App.Timezone != "Asia/Shanghai" {
		t.Errorf("app.timezone 默认值 = %q，期望 Asia/Shanghai", cfg.App.Timezone)
	}
	if cfg.Server.RequestTimeout != 0 {
		t.Errorf("server.request-timeout 默认值 = %v，期望 0（关闭，保持 Java 行为）", cfg.Server.RequestTimeout)
	}
}

func TestResolveTimezone(t *testing.T) {
	cases := []struct {
		name    string
		tz      string
		wantErr bool
	}{
		{name: "默认 Asia/Shanghai", tz: ""},
		{name: "显式 Asia/Shanghai", tz: "Asia/Shanghai"},
		{name: "UTC", tz: "UTC"},
		{name: "非法时区", tz: "Mars/Olympus", wantErr: true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			c := &Config{App: AppConfig{Timezone: tc.tz}}
			loc, err := c.ResolveTimezone()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("期望报错，实际得到 %v", loc)
				}
				return
			}
			if err != nil {
				t.Fatalf("ResolveTimezone(%q) 失败: %v", tc.tz, err)
			}
			if loc == nil {
				t.Fatal("返回的 Location 为 nil")
			}
		})
	}
}

// TestResolveTimezoneShanghaiOffset 确认上海时区固定为 +08:00（缺 tzdata 时也应如此）。
func TestResolveTimezoneShanghaiOffset(t *testing.T) {
	cfg := &Config{App: AppConfig{Timezone: "Asia/Shanghai"}}
	loc, err := cfg.ResolveTimezone()
	if err != nil {
		t.Fatalf("解析 Asia/Shanghai 失败: %v", err)
	}
	_, offset := time.Date(2026, 1, 1, 0, 0, 0, 0, loc).Zone()
	if offset != 8*3600 {
		t.Fatalf("Asia/Shanghai 偏移 = %d 秒，期望 28800", offset)
	}
}

// TestValidateExportDirRequiresAbsolute 对应报告 02 P1-8：
// 非 local 环境的导出目录必须是绝对路径，避免 Linux 上随 cwd 漂移。
func TestValidateExportDirRequiresAbsolute(t *testing.T) {
	base := func() *Config {
		c := &Config{}
		c.Server.Port = 9901
		c.Datasource.Datasource.Dynamic.Datasource.Master.URL = "jdbc:postgresql://localhost:5432/db"
		c.Datasource.Datasource.Dynamic.Datasource.Master.Username = "u"
		c.Redis.Host = "127.0.0.1"
		c.App.Env = "prod"
		c.Optimization.Export.Dir = "data/export" // 相对路径
		return c
	}

	if err := base().Validate(); err == nil {
		t.Fatal("prod + 相对导出目录应校验失败")
	}

	abs := base()
	abs.Optimization.Export.Dir = filepath.Join(t.TempDir(), "export")
	if err := abs.Validate(); err != nil {
		t.Fatalf("prod + 绝对导出目录应通过校验，实际: %v", err)
	}

	local := base()
	local.App.Env = "local"
	if err := local.Validate(); err != nil {
		t.Fatalf("local 环境允许相对导出目录，实际: %v", err)
	}
}
