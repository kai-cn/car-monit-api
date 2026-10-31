import io

p = 'src/handlers/query.rs'
s = io.open(p, encoding='utf-8').read()

s = s.replace('use axum::extract::{Json, Path, Query, State};',
              'use axum::extract::{Json, OriginalUri, Path, Query, State};')

s = s.replace('''fn time_range(c: &RawQuery) -> Result<(String, String), Response> {
    let start = c.get("startTime").cloned().unwrap_or_default();
    let end = c.get("endTime").cloned().unwrap_or_default();
    match require_time_range(&start, &end) {
        Ok(()) => Ok((start, end)),
        Err(e) => Err(json_status(
            StatusCode::BAD_REQUEST,
            json!({ "code": 400, "message": e.message() }),
        )),
    }
}''', '''fn time_range(c: &RawQuery, path: &str) -> Result<(String, String), Response> {
    let start = c.get("startTime").cloned().unwrap_or_default();
    let end = c.get("endTime").cloned().unwrap_or_default();
    match require_time_range(&start, &end) {
        Ok(()) => Ok((start, end)),
        Err(_) => Err(spring_bad_request(path)),
    }
}

/// 对应 Spring 缺少 @RequestParam 时的默认 400 响应体。
fn spring_bad_request(path: &str) -> Response {
    json_status(
        StatusCode::BAD_REQUEST,
        crate::router::spring_error(StatusCode::BAD_REQUEST, "Bad Request", path),
    )
}''')

# large_query: invalid ds -> 404; time_range path
s = s.replace('''pub async fn large_query(
    State(state): State<Arc<AppState>>,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    let ds = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return biz_map_error(e.message()),
    };
    let (start, end) = match time_range(&c) {''', '''pub async fn large_query(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    // Java 只有 /snapshot /fee /trail 三个映射；其余路径是 Spring 404。
    let ds = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(_) => {
            return json_status(
                StatusCode::NOT_FOUND,
                crate::router::spring_error(StatusCode::NOT_FOUND, "Not Found", uri.path()),
            )
        }
    };
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn car_track_by_car_no(State(state): State<Arc<AppState>>, Query(c): Query<RawQuery>) -> Response {
    let (start, end) = match time_range(&c) {''', '''pub async fn car_track_by_car_no(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    // @RequestParam String carNo 必填
    if c.get("carNo").map(|v| v.is_empty()).unwrap_or(true) {
        return spring_bad_request(uri.path());
    }
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn group_stats(State(state): State<Arc<AppState>>, Query(c): Query<RawQuery>) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c) {''', '''pub async fn group_stats(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    // @RequestParam String groupBy 必填
    if c.get("groupBy").map(|v| v.is_empty()).unwrap_or(true) {
        return spring_bad_request(uri.path());
    }
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn large_export_submit(
    State(state): State<Arc<AppState>>,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c) {''', '''pub async fn large_export_submit(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn sync_repair(State(state): State<Arc<AppState>>, Query(c): Query<RawQuery>) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c) {''', '''pub async fn sync_repair(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn unified_list(
    State(state): State<Arc<AppState>>,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c) {''', '''pub async fn unified_list(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c, uri.path()) {''')

s = s.replace('''pub async fn unified_export_submit(
    State(state): State<Arc<AppState>>,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c) {''', '''pub async fn unified_export_submit(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c, uri.path()) {''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('done')
