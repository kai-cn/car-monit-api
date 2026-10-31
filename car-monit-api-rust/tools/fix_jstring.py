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
                print('MISS', path, old[:70].replace('\n', ' '))
            s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)


# sysutil: JString RHS -> String for local variables / String fields
edit('src/services/sysutil.rs', [
    (r'= (section|toll|g|gantry|station|loc|item)\.(\w+)\.clone\(\);',
     r'= \1.\2.as_str().to_string();', True),
    (r'= (section|toll|g|gantry|station|loc|item)\.(\w+)\.clone\(\),',
     r'= \1.\2.as_str().to_string(),', True),
    ('info.trail_uuid = tracks.plate_key.clone();',
     'info.trail_uuid = tracks.plate_key.as_str().to_string();'),
    ('target.images_arry = utils::delete_end(&s);',
     'target.images_arry = utils::delete_end(&s);'),
])

# dict: map keys must be String
edit('src/services/dict.rs', [
    ('.map(|g| (g.gantry_code.clone(), g))', '.map(|g| (g.gantry_code.as_str().to_string(), g))'),
    ('.map(|t| (t.toll_code.clone(), t))', '.map(|t| (t.toll_code.as_str().to_string(), t))'),
    ('.map(|s| (s.section_code.clone(), s))', '.map(|s| (s.section_code.as_str().to_string(), s))'),
    ('m.insert(item.toll_code.clone(), item.clone());', 'm.insert(item.toll_code.as_str().to_string(), item.clone());'),
    ('m.insert(item.state_code_merge.clone(), item);', 'm.insert(item.state_code_merge.as_str().to_string(), item);'),
    ('m.insert(item.gantry_code.clone(), item.clone());', 'm.insert(item.gantry_code.as_str().to_string(), item.clone());'),
    ('Ok(list.into_iter().map(|g| (g.gantry_code.clone(), g)).collect())',
     'Ok(list.into_iter().map(|g| (g.gantry_code.as_str().to_string(), g)).collect())'),
    ('Ok(list.into_iter().map(|s| (s.section_code.clone(), s)).collect())',
     'Ok(list.into_iter().map(|s| (s.section_code.as_str().to_string(), s)).collect())'),
])

# base handlers
edit('src/handlers/base.rs', [
    ('.map(|g| (g.gantry_code.clone(), g))', '.map(|g| (g.gantry_code.as_str().to_string(), g))'),
    ('r.vehicleplate = vehicleplate[..idx].to_string();', 'r.vehicleplate = vehicleplate[..idx].to_string().into();'),
    ('gantry_map.get(&r.gantryid)', 'gantry_map.get(r.gantryid.as_str())'),
    ('r.gantry_name = g.gantry_name.clone();', 'r.gantry_name = g.gantry_name.as_str().to_string();'),
    ('r.section_code_str = g.section_code.clone();', 'r.section_code_str = g.section_code.as_str().to_string();'),
    ('r.snappicturepath = utils::replace_pic_url(&utils::delete_end(&r.snappicturepath));',
     'r.snappicturepath = utils::replace_pic_url(&utils::delete_end(&r.snappicturepath)).into();'),
])

# sync ids
edit('src/services/sync.rs', [
    ('id: r.datauuid.clone(),', 'id: r.datauuid.as_str().to_string(),'),
    ('id: r.cid.clone(),', 'id: r.cid.as_str().to_string(),'),
])

# progressive struct literal fields
s = io.open('src/services/progressive.rs', encoding='utf-8').read()
for f in ['start_time', 'end_time', 'platenumber', 'gantryname', 'roadname', 'sectionname', 'orgname', 'tollname']:
    s = s.replace('%s: req.%s.clone(),' % (f, f), '%s: req.%s.clone().into(),' % (f, f))
s = s.replace('vehicleplate: req.platenumber.clone(),', 'vehicleplate: req.platenumber.clone().into(),')
s = s.replace('in_apply_time1: req.start_time.clone(),', 'in_apply_time1: req.start_time.clone().into(),')
s = s.replace('in_apply_time2: req.end_time.clone(),', 'in_apply_time2: req.end_time.clone().into(),')
io.open('src/services/progressive.rs', 'w', encoding='utf-8', newline='\n').write(s)

print('done')
