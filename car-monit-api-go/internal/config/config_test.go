package config

// 配置加载与新增开关的回归护栏（报告 01 Q7 / 报告 02 P0-3/P0-5/P0-7/P1-8）。

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestLoadExampleConfig 保证仓库里的最小示例能被真实解析并通过校验，
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

// TestLoadMergesLocalOverride 锁住「基线 + 本地覆盖」的合并语义（凭据卫生的基石）：
// 主文件不含口令，口令只在 <name>.local.yaml 里；合并后应拿到覆盖值。
func TestLoadMergesLocalOverride(t *testing.T) {
	dir := t.TempDir()
	base := filepath.Join(dir, "config.yaml")
	writeFile(t, base, `
spring:
  datasource:
    dynamic:
      datasource:
        master:
          url: jdbc:postgresql://db.example.internal:5432/RuoYi
          username: gaussdb
          password: ""
redis:
  host: 127.0.0.1
`)
	local := filepath.Join(dir, "config.local.yaml")
	writeFile(t, local, `
spring:
  datasource:
    dynamic:
      datasource:
        master:
          password: "from-local-override"
`)

	cfg, err := Load(base)
	if err != nil {
		t.Fatalf("加载失败: %v", err)
	}
	if got := cfg.Datasource.Master().Password; got != "from-local-override" {
		t.Fatalf("密码未被本地覆盖文件合并，实际 %q", got)
	}
	// 未在覆盖文件里出现的键必须保留基线的值
	if got := cfg.Datasource.Master().Username; got != "gaussdb" {
		t.Fatalf("覆盖合并破坏了基线键，username = %q", got)
	}
	if cfg.LoadedOverride() != local {
		t.Fatalf("LoadedOverride = %q，期望 %q", cfg.LoadedOverride(), local)
	}
}

// TestLoadWithoutOverride 确认没有本地覆盖文件时行为不变（LoadedOverride 为空）。
func TestLoadWithoutOverride(t *testing.T) {
	dir := t.TempDir()
	base := filepath.Join(dir, "config.yaml")
	writeFile(t, base, `
spring:
  datasource:
    dynamic:
      datasource:
        master:
          url: jdbc:postgresql://db.example.internal:5432/RuoYi
          username: gaussdb
          password: "p@ss"
redis:
  host: 127.0.0.1
`)

	cfg, err := Load(base)
	if err != nil {
		t.Fatalf("加载失败: %v", err)
	}
	if cfg.LoadedOverride() != "" {
		t.Fatalf("没有覆盖文件时 LoadedOverride 应为空，实际 %q", cfg.LoadedOverride())
	}
	if cfg.Datasource.Master().Password != "p@ss" {
		t.Fatalf("密码读取错误: %q", cfg.Datasource.Master().Password)
	}
}

// TestBaselineConfigsContainNoSecrets 是凭据卫生的回归护栏：
// 入库的三份配置（config.yaml / config.verify.yaml / config.example.yaml）不得出现口令。
//
// 做法：把每份文件复制到临时目录（不带 .local 覆盖）再 Load，
// 这样校验的是"入库内容本身"，而不是本机 config.local.yaml 合并后的结果。
func TestBaselineConfigsContainNoSecrets(t *testing.T) {
	files := []string{"config.yaml", "config.verify.yaml", "config.example.yaml"}
	for _, name := range files {
		src := filepath.Join("..", "..", "configs", name)
		raw, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("读取 %s 失败: %v", name, err)
		}
		if strings.Contains(string(raw), "OpenGauss") || strings.Contains(string(raw), "changeme") {
			t.Fatalf("%s 仍包含已知历史口令字面量", name)
		}

		dir := t.TempDir()
		isolated := filepath.Join(dir, "config.yaml")
		writeFile(t, isolated, string(raw))
		cfg, err := Load(isolated)
		if err != nil {
			t.Fatalf("%s 必须能独立加载（口令为空也应通过 Validate）: %v", name, err)
		}
		secrets := map[string]string{
			"database": cfg.Datasource.Master().Password,
			"redis":    cfg.Redis.Password,
			"es":       cfg.Elasticsearch.Password,
			"rabbitmq": cfg.RabbitMQ.Password,
		}
		for label, secret := range secrets {
			if secret != "" {
				t.Fatalf("%s 的 %s 口令写进了入库配置（应为空，由 env/local 覆盖注入）", name, label)
			}
		}
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("写入 %s 失败: %v", path, err)
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
