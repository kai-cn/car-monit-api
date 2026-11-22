# -*- coding: utf-8 -*-
"""给 middleware.rs 打「Tomcat 容器级 400」补丁。

middleware.rs 里有一个裸 NUL 字符（早期补丁写进了 char 字面量），Edit 工具没法精确匹配，
所以这段用 Python 按标记做区间替换；顺带把那行换成 '\\u{0}'，源文件恢复纯文本。
"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 'src', 'middleware.rs')

START = '/// Spring 的协商与 /error 渲染规则'
END = '    req.extensions_mut().insert(OriginalPath(original));\n'

NEW = '''/// Tomcat 错误页的固定样式块。
const TOMCAT_CSS: &str = "body {font-family:Tahoma,Arial,sans-serif;} h1, h2, h3, b {color:white;background-color:#525D76;} h1 {font-size:22px;} h2 {font-size:16px;} h3 {font-size:14px;} p {font-size:12px;} a {color:black;} .line {height:1px;background-color:#525D76;border:none;}";

/// 容器级 400：请求行本身被 Tomcat 拒掉（编码斜杠、NUL、超过 maxHttpHeaderSize），
/// 请求根本没进 Spring，所以既不走 Whitelabel 也不看 Accept —— 实测恒为这一页（435 字节）。
fn tomcat_bad_request() -> Response {
    let title = "HTTP Status 400 \\u{2013} Bad Request";
    let body = format!(
        "<!doctype html><html lang=\\"en\\"><head><title>{}</title><style type=\\"text/css\\">{}</style></head><body><h1>{}</h1></body></html>",
        title, TOMCAT_CSS, title
    );
    Response::builder()
        .status(StatusCode::BAD_REQUEST)
        .header(
            axum::http::header::CONTENT_TYPE,
            HeaderValue::from_static("text/html;charset=utf-8"),
        )
        .body(Body::from(body))
        .unwrap()
}

/// 请求行级（`path?query`）的 Tomcat 拒绝条件。
fn container_rejects(request_line: &str) -> bool {
    let lower = request_line.to_ascii_lowercase();
    // PARITY: Tomcat 默认拒绝编码后的斜杠与 NUL（实测 `/base/gantry/list%2F..%2F..` → 容器 HTML 400），
    // 判定范围是整个请求行（含 query），不只是 path。
    if lower.contains("%2f") || lower.contains("%00") || request_line.contains('\\u{0}') {
        return true;
    }
    // PARITY: Tomcat 的 maxHttpHeaderSize=8192 连请求行一起算，实测 GET 的
    // `path?query` 上限 8075 字节（8075 → 200，8076 → 400）。长参数（例如把整段轨迹
    // JSON 当过滤值传进来）在 Java 会撞这个闸门，hyper 默认不撞，状态码就差一位。
    request_line.len() > MAX_URI_BYTES
}

/// Spring 的协商与 /error 渲染规则（实测得到）：
///   1. 请求行先过 Tomcat 的容器级闸门（编码斜杠 / NUL / 长度上限）；
///   2. 路径按 AntPathMatcher 归一化；
///   3. 处理器成功返回 2xx 而客户端不接受 JSON → 406；404/405/500 的状态码优先，不被改写成 406；
///   4. 任何 >=400 的响应，体由 Accept 决定：text/html|text/* → Whitelabel；JSON 族或 */* → JSON；
///      两者都不接受 → 空体且不带 Content-Type。
pub async fn spring_negotiation(mut req: Request, next: Next) -> Response {
    let original = req.uri().path().to_string();
    let request_line = match req.uri().query() {
        Some(q) => format!("{}?{}", original, q),
        None => original.clone(),
    };
    if container_rejects(&request_line) {
        return tomcat_bad_request();
    }
    let norm = normalize_path(&original);
    if norm != original {
        // http::Uri 没有 set_path，按 origin-form 重建 path?query
        let rebuilt = match req.uri().query() {
            Some(q) => format!("{}?{}", norm, q),
            None => norm.clone(),
        };
        if let Ok(uri) = rebuilt.parse::<axum::http::Uri>() {
            *req.uri_mut() = uri;
        }
    }
    let accept_raw = req
        .headers()
        .get(ACCEPT)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_string();
    let (json_ok, html_ok) = accept_prefs(&accept_raw);
    req.extensions_mut().insert(OriginalPath(original));
'''


def main():
    src = io.open(P, encoding='utf-8').read()
    i = src.index(START)
    j = src.index(END, i) + len(END)
    old = src[i:j]
    assert '\x00' in old, '预期这段里有裸 NUL 字符'
    src2 = src[:i] + NEW + src[j:]
    assert '\x00' not in src2, '替换后仍有裸 NUL'
    io.open(P, 'w', encoding='utf-8', newline='\n').write(src2)
    print('patched middleware.rs: %d -> %d bytes' % (len(old), len(NEW)))


if __name__ == '__main__':
    sys.exit(main())
