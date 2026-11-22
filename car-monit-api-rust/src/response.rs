// 来源: pro-base-common/src/main/java/com/ruoyi/common/core/domain/AjaxResult.java
//       pro-base-common/src/main/java/com/ruoyi/common/core/page/TableDataInfo.java
//       pro-base-common/src/main/java/com/ruoyi/common/core/domain/R.java
//       pro-base-common/src/main/java/com/ruoyi/common/constant/HttpStatus.java
// 职责: 复刻 RuoYi 的 {code,msg,data} / {total,rows,code,msg} 响应壳。
// 对应关系:
//   AjaxResult.success(data)   ↔ Response::success(data)
//   BaseController.getDataTable ↔ Response::table(rows,total)
//   AjaxResult.error(code,msg)  ↔ Response::fail_code(code,msg)

use serde::Serialize;
use serde_json::{json, Value};

pub const CODE_SUCCESS: i32 = 200;
pub const CODE_WARN: i32 = 601;
pub const CODE_ERROR: i32 = 500;

/// 对应 AjaxResult extends HashMap<String,Object>。
/// DIFF: Java 的 AjaxResult 是 Map，可以任意 put 扩展键；Rust 用 serde_json::Value
/// 保留同样的动态性，同时保证键顺序（preserve_order）。
/// PARITY: Java 侧是 HashMap，`{"msg","code","data"}` 是它实际的迭代顺序（实测稳定），
/// 因此这里按 msg → code → data 的顺序拼装，保证响应体字节序也一致。
#[derive(Debug, Clone, Serialize)]
pub struct AjaxResult(pub Value);

/// 按 Java HashMap 的观测顺序生成外壳：msg、code，然后可选 data。
fn envelope(code: i32, msg: String, data: Option<Value>) -> Value {
    let mut m = serde_json::Map::new();
    m.insert("msg".to_string(), json!(msg));
    m.insert("code".to_string(), json!(code));
    if let Some(d) = data {
        m.insert("data".to_string(), d);
    }
    Value::Object(m)
}

impl AjaxResult {
    pub fn new(code: i32, msg: impl Into<String>) -> Self {
        Self(envelope(code, msg.into(), None))
    }

    /// AjaxResult.success(data)：data 为 None 时省略 data 键（Java 的 isNotNull 判断）。
    pub fn success(data: Option<Value>) -> Self {
        Self(envelope(CODE_SUCCESS, "操作成功".into(), data))
    }

    pub fn success_msg(msg: impl Into<String>) -> Self {
        Self(envelope(CODE_SUCCESS, msg.into(), None))
    }

    pub fn success_with(msg: impl Into<String>, data: Option<Value>) -> Self {
        Self(envelope(CODE_SUCCESS, msg.into(), data))
    }

    pub fn warn(msg: impl Into<String>, data: Option<Value>) -> Self {
        Self(envelope(CODE_WARN, msg.into(), data))
    }

    pub fn error(msg: impl Into<String>) -> Self {
        Self::new(CODE_ERROR, msg)
    }

    pub fn fail_code(code: i32, msg: impl Into<String>) -> Self {
        Self::new(code, msg)
    }

    pub fn put(mut self, key: &str, value: Value) -> Self {
        if let Some(obj) = self.0.as_object_mut() {
            obj.insert(key.to_string(), value);
        }
        self
    }
}

/// 对应 TableDataInfo；JSON 键名与 Java 完全一致。
#[derive(Debug, Clone, Serialize)]
pub struct TableDataInfo {
    pub total: i64,
    pub rows: Value,
    pub code: i32,
    pub msg: String,
}

impl TableDataInfo {
    /// 对应 BaseController.getDataTable(list)：code=200、msg=查询成功。
    pub fn new(rows: Value, total: i64) -> Self {
        Self {
            total,
            rows,
            code: CODE_SUCCESS,
            msg: "查询成功".into(),
        }
    }

    pub fn with_msg(rows: Value, total: i64, msg: impl Into<String>) -> Self {
        Self {
            total,
            rows,
            code: CODE_SUCCESS,
            msg: msg.into(),
        }
    }
}

/// 对应 R<T>：{code,msg,data}，成功 200，失败 500。
#[derive(Debug, Clone, Serialize)]
pub struct R<T> {
    pub code: i32,
    pub msg: String,
    pub data: Option<T>,
}

impl<T> R<T> {
    pub fn ok(data: Option<T>) -> Self {
        Self {
            code: CODE_SUCCESS,
            msg: "操作成功".into(),
            data,
        }
    }
    pub fn fail(msg: impl Into<String>) -> Self {
        Self {
            code: CODE_ERROR,
            msg: msg.into(),
            data: None,
        }
    }
}
