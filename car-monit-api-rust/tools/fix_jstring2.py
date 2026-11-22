import io
import re


def edit(path, pairs, regex=False):
    s = io.open(path, encoding='utf-8').read()
    for item in pairs:
        old, new = item[0], item[1]
        use_re = bool(item[2]) if len(item) > 2 else regex
        if use_re:
            s, n = re.subn(old, new, s)
            if n == 0:
                print('MISS-RE', path, old)
        else:
            if old not in s:
                print('MISS', path, old[:80].replace('\n', ' '))
            s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)


# repo: Cond value args accept both String/JString via Into
edit('src/repo/mod.rs', [
    (r'Cond::(Eq|Like|Gte|Lte)\(("[^"]+"), ([^()]+\.clone\(\))\)', r'Cond::\1(\2, \3.into())', True),
])

# multisource
edit('src/services/multisource.rs', [
    ('uuid: format!("{}-{}", plate, uuid::Uuid::new_v4().simple()),',
     'uuid: format!("{}-{}", plate, uuid::Uuid::new_v4().simple()).into(),'),
    ('trail_uuid: tracks.uuid.clone(),', 'trail_uuid: tracks.uuid.to_string(),'),
])

# track_sync
edit('src/services/track_sync.rs', [
    ('plate_key: car_no.clone(),', 'plate_key: car_no.clone().into(),'),
    ('uuid: format!("{}@@{}", car_no, today),', 'uuid: format!("{}@@{}", car_no, today).into(),'),
    ('merged.iter().map(|r| r.uuid.clone()).collect()', 'merged.iter().map(|r| r.uuid.as_str().to_string()).collect()'),
    ('seen.insert(o.uuid.clone())', 'seen.insert(o.uuid.as_str().to_string())'),
])

# trail enrich assignments (TrailBo fields are String)
edit('src/services/trail.rs', [
    (r'point\.(\w+) = (loc|g|t|ip)\.(\w+)\.clone\(\);', r'point.\1 = \2.\3.as_str().to_string();', True),
    ('trail_uuid: tracks.uuid.clone(),', 'trail_uuid: tracks.uuid.to_string(),'),
    ('tracks.trail_points = serde_json::to_string(&points).unwrap_or_default();',
     'tracks.trail_points = serde_json::to_string(&points).unwrap_or_default().into();'),
    ('tracks.trail_points = serde_json::to_string(&all).unwrap_or_default();',
     'tracks.trail_points = serde_json::to_string(&all).unwrap_or_default().into();'),
    ('tracks.plate_key = trails[0]\n                .tracks\n                .as_deref()\n                .map(|t| t.plate_key.clone())\n                .unwrap_or_default();',
     'tracks.plate_key = trails[0]\n                .tracks\n                .as_deref()\n                .map(|t| t.plate_key.clone())\n                .unwrap_or_default();'),
])
print('done')
