package utils

import (
	"errors"
	"net/url"
	"testing"
)

func TestRedactStringExplicitSecret(t *testing.T) {
	got := RedactString("connect failed: password=hunter2 host=db", "hunter2")
	want := "connect failed: password=*** host=db"
	if got != want {
		t.Fatalf("脱敏结果 = %q，期望 %q", got, want)
	}
}

func TestRedactStringURLEncodedSecret(t *testing.T) {
	secret := "p@ss/w0rd"
	got := RedactString("dsn=postgres://u:"+url.QueryEscape(secret)+"@host/db", secret)
	if got != "dsn=postgres://u:***@host/db" {
		t.Fatalf("URL-encoded 口令未脱敏: %q", got)
	}
}

func TestRedactStringKeyValueFallback(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"failed to connect to `host=db user=u database=d`: password=abc123", "failed to connect to `host=db user=u database=d`: password=***"},
		{"dial tcp: pwd=zzz timeout", "dial tcp: pwd=*** timeout"},
		{"auth error token=abcdef", "auth error token=***"},
		// 键名保留，值必须消失
		{"secret=topsecret", "secret=***"},
	}
	for _, tc := range cases {
		if got := RedactString(tc.in); got != tc.want {
			t.Errorf("RedactString(%q) = %q，期望 %q", tc.in, got, tc.want)
		}
	}
}

func TestRedactStringIgnoresShortAndEmptySecret(t *testing.T) {
	// 空串不能把文本撕碎
	if got := RedactString("hello world", ""); got != "hello world" {
		t.Fatalf("空 secret 不应改变文本，实际 %q", got)
	}
	// 长度为 1 的 secret 不做原值替换（会误伤正常字符）
	if got := RedactString("a normal sentence", "a"); got != "a normal sentence" {
		t.Fatalf("短 secret 不应做原值替换，实际 %q", got)
	}
}

func TestRedactError(t *testing.T) {
	if RedactError(nil) != nil {
		t.Fatal("nil error 应返回 nil")
	}
	err := errors.New("ping failed: password=s3cr3t")
	got := RedactError(err, "s3cr3t")
	if got.Error() != "ping failed: password=***" {
		t.Fatalf("错误未脱敏: %q", got.Error())
	}
	// 脱敏后不再保留原始错误链（避免通过 errors.Unwrap 拿到明文）
	if errors.Unwrap(got) != nil {
		t.Fatal("脱敏后的 error 不应保留 Unwrap 链")
	}
}
