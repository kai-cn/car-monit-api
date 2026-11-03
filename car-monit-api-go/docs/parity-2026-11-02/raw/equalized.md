| 用例 | 请求 | 判定 | Java | Go | 差异摘要 | 稳定 |
|---|---|---|---|---|---|---|
| bad-json-post | `POST /base/sysutil/changeTrailInfo` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| empty-post | `POST /base/sysutil/changeTrailInfo` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| trailing-slash | `GET /base/gantry/list/?pageSize=1` | STATUS | 200 | 404 | java=200 go=404 | 否(重试后一致) |
| feeGantry-filter-actualfeeclass | `GET /base/feeGantry/list?pageNum=1&pageSize=5&actualfeeclass=1` | NONDET | 200 | 200 | `rows[bigId="237"].id`(VALUE); `rows[bigId="269"].id`(VALUE); `rows[bigId="58"].id`(VALUE); `rows[bigId="59"].id`(VALUE); `rows[bigId="89"].id`(VALUE) | 是 |
| feeGantry-filter-axlecount | `GET /base/feeGantry/list?pageNum=1&pageSize=5&axlecount=6` | NONDET | 200 | 200 | `rows[bigId="237"].id`(VALUE); `rows[bigId="269"].id`(VALUE); `rows[bigId="317"].id`(VALUE); `rows[bigId="59"].id`(VALUE); `rows[bigId="89"].id`(VALUE) | 是 |
| feeGantry-filter-createtime | `GET /base/feeGantry/list?pageNum=1&pageSize=5&createtime=2024-11-11T10` | NONDET | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="4"]`(ONLY_JAVA); `rows[bigId="407"]`(ONLY_JAVA); `rows[bigId="420"]`(ONLY_JAVA); `rows[bigId="58"]`(ONLY_JAVA) …共 8 项 | 是 |
| feeGantry-filter-discountfee | `GET /base/feeGantry/list?pageNum=1&pageSize=5&discountfee=1388` | NONDET | 200 | 200 | `rows[bigId="271"].id`(VALUE); `rows[bigId="275"].id`(VALUE); `rows[bigId="327"].id`(VALUE); `rows[bigId="339"].id`(VALUE); `rows[bigId="59"].id`(VALUE) | 是 |
| feeGantry-full-set | `GET /base/feeGantry/list?pageNum=1&pageSize=200` | NONDET | 200 | 200 | `rows[bigId="100"].id`(VALUE); `rows[bigId="1006"].id`(VALUE); `rows[bigId="1020"].id`(VALUE); `rows[bigId="1036"].id`(VALUE); `rows[bigId="1062"].id`(VALUE); `rows[bigId="1087"].id`(VALUE) …共 200 项 | 是 |
| feeGantry-list-bigpagesize | `GET /base/feeGantry/list?pageNum=1&pageSize=5000` | NONDET | 200 | 200 | `rows[bigId="100"].id`(VALUE); `rows[bigId="1006"].id`(VALUE); `rows[bigId="1020"].id`(VALUE); `rows[bigId="1036"].id`(VALUE); `rows[bigId="1062"].id`(VALUE); `rows[bigId="1087"].id`(VALUE) …共 200 项 | 是 |
| feeGantry-list-default | `GET /base/feeGantry/list?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `rows[bigId="4"].id`(VALUE); `rows[bigId="407"].id`(VALUE); `rows[bigId="420"].id`(VALUE); `rows[bigId="58"].id`(VALUE); `rows[bigId="59"].id`(VALUE) | 是 |
| feeGantry-list-farpage | `GET /base/feeGantry/list?pageNum=99999&pageSize=5` | NONDET | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="3891"]`(ONLY_JAVA); `rows[bigId="4242"]`(ONLY_JAVA); `rows[bigId="4430"]`(ONLY_JAVA); `rows[bigId="4661"]`(ONLY_JAVA) …共 7 项 | 是 |
| feeGantry-list-noargs | `GET /base/feeGantry/list` | NONDET | 200 | 200 | `rows[bigId="1103"].id`(VALUE); `rows[bigId="4"].id`(VALUE); `rows[bigId="407"].id`(VALUE); `rows[bigId="420"].id`(VALUE); `rows[bigId="423"].id`(VALUE); `rows[bigId="58"].id`(VALUE) …共 10 项 | 是 |
| feeGantry-list-order | `GET /base/feeGantry/list?pageNum=1&pageSize=5&orderByColumn=bigId&isAs` | NONDET | 200 | 200 | `rows[bigId="4"]`(ONLY_GO); `rows[bigId="407"]`(ONLY_GO); `rows[bigId="420"]`(ONLY_GO); `rows[bigId="58"]`(ONLY_GO); `rows[bigId="59"]`(ONLY_GO); `rows[bigId="969"]`(ONLY_JAVA) …共 10 项 | 是 |
| feeGantry-list-page2 | `GET /base/feeGantry/list?pageNum=2&pageSize=5` | NONDET | 200 | 200 | `rows[bigId="1103"].id`(VALUE); `rows[bigId="423"].id`(VALUE); `rows[bigId="795"].id`(VALUE); `rows[bigId="829"].id`(VALUE); `rows[bigId="984"].id`(VALUE) | 是 |
| feerecords-list-bigpagesize | `GET /base/feerecords/list?pageNum=1&pageSize=5000` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-default | `GET /base/feerecords/list?pageNum=1&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-farpage | `GET /base/feerecords/list?pageNum=99999&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-noargs | `GET /base/feerecords/list` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-order | `GET /base/feerecords/list?pageNum=1&pageSize=5&orderByColumn=bigId&isA` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-page2 | `GET /base/feerecords/list?pageNum=2&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-pagesize-1 | `GET /base/feerecords/list?pageNum=1&pageSize=-1` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-list-pagesize0 | `GET /base/feerecords/list?pageNum=1&pageSize=0` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| feerecords-listToExport | `GET /base/feerecords/listToExport?pageNum=1&pageSize=5` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-filter-agentPk | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&agentPk=1` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-filter-yxtzj | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&yxtzj=45L4479928780847000` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| fwqjcxx-info-miss | `GET /base/fwqjcxx/__no_such_id__` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| prog-feerecords | `GET /progressive/feerecords/list?startTime=2025-10-01+00%3A00%3A00&end` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| prog-trailfitting | `GET /progressive/trailfitting/list?startTime=2025-10-01+00%3A00%3A00&e` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| sfsjcxx-filter-agentPk | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&agentPk=d2c6df4afa7ff18d48` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| snapshotflow-filter-direction | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&direction=1` | NONDET | 200 | 200 | `rows[id="1e76db85875749f6a9146a53e91cee91"]`(ONLY_JAVA); `rows[id="31b517a7-1ce8-4b27-98df-79f49ce40e57"]`(ONLY_GO); `rows[id="34857c6a-d158-4edb-b39c-468408deb6c9"]`(ONLY_GO); `rows[id="6d24148e0a2b4fb1b0a1bdc9f528cbf7"]`(ONLY_JAVA); `rows[id="881e63e46bfe4ecbbc6f8b61cbb59bd4"]`(ONLY_JAVA); `rows[id="89df0302-a112-4ba0-8184-fbc6c06f34b9"]`(ONLY_GO) …共 11 项 | 是 |
| snapshotflow-filter-gantryname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&gantryname=%E9%9F%B6%` | NONDET | 200 | 200 | `rows[id="094502ed-537b-4c7f-b220-34248810538a"]`(ONLY_GO); `rows[id="1f9b58c673ad4efa91b1e515c8d00714"]`(ONLY_JAVA); `rows[id="29a2c1d3-3ab4-4a6c-98b6-5b826ca00c21"]`(ONLY_GO); `rows[id="69deb941f0954917bc36b39fddcdf8dc"]`(ONLY_JAVA); `rows[id="8a4a6021-06c9-4e21-8865-10a1771dc18d"]`(ONLY_GO); `rows[id="9e042bdd65264c11ad58d89efa53eba9"]`(ONLY_JAVA) …共 10 项 | 是 |
| snapshotflow-filter-roadname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&roadname=%E5%A4%A7%E5` | NONDET | 200 | 200 | `rows[id="0f624290-adc2-4c02-9c62-dea4349c5542"]`(ONLY_GO); `rows[id="1933d486cf8b4af58bb0151fcf0ccdc8"]`(ONLY_JAVA); `rows[id="685836ad1f7e44c99efe6128168e6bb3"]`(ONLY_JAVA); `rows[id="81ed181eabc14491876cc5629f43d1b7"]`(ONLY_JAVA); `rows[id="939a5fbb4fbf448fa6909e631cda341d"]`(ONLY_JAVA); `rows[id="c2a9602df7ee43f18beb9a162170f40b"]`(ONLY_JAVA) …共 11 项 | 是 |
| snapshotflow-filter-sectionname | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&sectionname=%E6%B3%B0` | NONDET | 200 | 200 | `rows[id="1120dce2e89e4584a579e979e55a348b"]`(ONLY_JAVA); `rows[id="1c81f3f6-aab0-4925-8d9d-7e07eac046e2"]`(ONLY_GO); `rows[id="64bbcf1174cc40fba7c62105389535d0"]`(ONLY_JAVA); `rows[id="6d18b2e544fa439c8465792cd39d8979"]`(ONLY_JAVA); `rows[id="8af82d5353414aa18c53688f6eb482d4"]`(ONLY_JAVA); `rows[id="91acc46e5f904ae9bf66868e083a54c1"]`(ONLY_JAVA) …共 11 项 | 是 |
| snapshotflow-full-set | `GET /base/snapshotflow/list?pageNum=1&pageSize=251` | NONDET | 200 | 200 | `rows[id="001fda2c7e0b4f3a921f591a0950f6f0"]`(ONLY_JAVA); `rows[id="002e4aeeecb64764abadf2bdfc8f3ba6"]`(ONLY_JAVA); `rows[id="007b2717c4da4cbc95b1d30261be7a4c"]`(ONLY_JAVA); `rows[id="0110bbfed9fa4f169cf442ff3c341778"]`(ONLY_JAVA); `rows[id="02709ba519d041129e4ec272460b08a1"]`(ONLY_JAVA); `rows[id="0379472e50d64c39b8fad90e14b07f6e"]`(ONLY_JAVA) …共 503 项 | 是 |
| snapshotflow-list-bigpagesize | `GET /base/snapshotflow/list?pageNum=1&pageSize=5000` | NONDET | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="003352ee39bf4ada8f0b22e967d46876"]`(ONLY_JAVA); `rows[id="009cc94fc06246ebbf4f6bf3498f7514"]`(ONLY_JAVA); `rows[id="00e2e06f-d531-4e12-aa98-b1cdd6fb9c6a"]`(ONLY_GO); `rows[id="0150070a-3097-421c-967b-192dd644d74f"]`(ONLY_GO) …共 1154 项 | 是 |
| snapshotflow-list-default | `GET /base/snapshotflow/list?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `rows[id="031446109fb643f59645c2495e8e6851"]`(ONLY_JAVA); `rows[id="2bdad185-0f6b-4550-8f85-e8ebc6c6f71d"]`(ONLY_GO); `rows[id="389ed49265b94ae9b965d468ffb38e96"]`(ONLY_JAVA); `rows[id="38ac2af7df8b4b628b7563bcd334ba5c"]`(ONLY_JAVA); `rows[id="79c21194-3a7d-4765-a5aa-b68a1ba27ed0"]`(ONLY_GO); `rows[id="83ac07c1-3602-45e0-b164-0f69fc439f59"]`(ONLY_GO) …共 11 项 | 是 |
| snapshotflow-list-farpage | `GET /base/snapshotflow/list?pageNum=99999&pageSize=5` | NONDET | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="2a4634aec10f4b85acfaffbf32693b52"]`(ONLY_JAVA); `total`(VALUE) | 是 |
| snapshotflow-list-noargs | `GET /base/snapshotflow/list` | NONDET | 200 | 200 | `rows[id="1a4f7e378ad543f19a858b3f122c7b81"]`(ONLY_JAVA); `rows[id="1fc7bcb83c0f47f7832f93c9ddd97a58"]`(ONLY_JAVA); `rows[id="22201eda-8947-46c7-b9ee-6a6e9d66f4d3"]`(ONLY_GO); `rows[id="42bba00e7c41445bbca0ba926517275b"]`(ONLY_JAVA); `rows[id="4340b0bc45c14a79962efea7ff526d2f"]`(ONLY_JAVA); `rows[id="4358d9644c494ed288f5022005e3ff55"]`(ONLY_JAVA) …共 21 项 | 是 |
| snapshotflow-list-order | `GET /base/snapshotflow/list?pageNum=1&pageSize=5&orderByColumn=id&isAs` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| snapshotflow-list-page2 | `GET /base/snapshotflow/list?pageNum=2&pageSize=5` | NONDET | 200 | 200 | `rows[id="1977672686d846a8ab55422e588bc543"]`(ONLY_JAVA); `rows[id="3014831f79f34138a7240db7c1923890"]`(ONLY_JAVA); `rows[id="33f03809ecad4ef9a8362162bd7d22cb"]`(ONLY_JAVA); `rows[id="a2822987-22ac-407c-a569-1856002be562"]`(ONLY_GO); `rows[id="af2245fe-fd2c-41d8-81ad-2157e908de90"]`(ONLY_GO); `rows[id="ce11fe03e29e4526a666c429c8736158"]`(ONLY_JAVA) …共 11 项 | 是 |
| snapshotflow-listToExport | `GET /base/snapshotflow/listToExport?pageNum=1&pageSize=5` | NONDET | 200 | 200 | `[id="326d7596-a1c8-42a2-8a01-4ab78a4963bd"]`(ONLY_GO); `[id="3dd4e908f69745ae8653747b590b3b6b"]`(ONLY_JAVA); `[id="58718e0f71164bd2a4941d61a826ddd8"]`(ONLY_JAVA); `[id="893f41dad1574951b58fd786f2c1925b"]`(ONLY_JAVA); `[id="a274c248-c847-4879-8d99-e63d8fe2769c"]`(ONLY_GO); `[id="b29bea3f283f44ae90aa8f06426429c2"]`(ONLY_JAVA) …共 10 项 | 是 |
| cartrack-by-carno | `GET /base/sysutil/carTrackQueryByCarNo?plateNo=%E8%B5%A3AF12345&startT` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| cartrack-by-time | `GET /base/sysutil/carTrackQueryByTime?startTime=2025-10-01+00%3A00%3A0` | STATUS | 400 | 200 | java=400 go=200 | 否(重试后一致) |
| trailtracks-info | `GET /base/trailtracks/e0e22490-fb40-4795-947b-68565d864aa7?uuid=e0e224` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-dataSource | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&dataSource=ZdTrails%` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-dataType | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&dataType=weigh` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-plateNo | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&plateNo=%E8%BD%A6%E7` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-filter-siteId | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&siteId=4` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| vehicleweight-list-order | `GET /base/vehicleweight/list?pageNum=1&pageSize=5&orderByColumn=uuid&i` | STATUS | 500 | 200 | java=500 go=200 | 否(重试后一致) |
| 404-deep | `GET /base/notatable/list` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 404-path | `GET /no/such/endpoint` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 405-info-delete | `DELETE /base/gantry/18` | DIFF | 405 | 405 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| 405-list-post | `POST /base/gantry/list` | DIFF | 405 | 405 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| feeGantry-list-pagesize-1 | `GET /base/feeGantry/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="1103"]`(ONLY_GO); `rows[bigId="4"]`(ONLY_GO); `rows[bigId="407"]`(ONLY_GO); `rows[bigId="420"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| feeGantry-list-pagesize0 | `GET /base/feeGantry/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="1103"]`(ONLY_GO); `rows[bigId="4"]`(ONLY_GO); `rows[bigId="407"]`(ONLY_GO); `rows[bigId="420"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| feeStationEnter-list-farpage | `GET /base/feeStationEnter/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=89378151]`(ONLY_JAVA); `rows[bigId=89380527]`(ONLY_JAVA) | 否(重试后一致) |
| feeStationEnter-list-order | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&orderByColumn=bigI` | DIFF | 200 | 200 | `rows[bigId=2308]`(ONLY_GO); `rows[bigId=2324]`(ONLY_GO); `rows[bigId=2326]`(ONLY_GO); `rows[bigId=2344]`(ONLY_GO); `rows[bigId=2386]`(ONLY_GO); `rows[bigId=89380029]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| feeStationEnter-list-pagesize-1 | `GET /base/feeStationEnter/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=2308]`(ONLY_GO); `rows[bigId=2324]`(ONLY_GO); `rows[bigId=2326]`(ONLY_GO); `rows[bigId=2344]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| feeStationEnter-list-pagesize0 | `GET /base/feeStationEnter/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=2308]`(ONLY_GO); `rows[bigId=2324]`(ONLY_GO); `rows[bigId=2326]`(ONLY_GO); `rows[bigId=2344]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| feestationexit-list-farpage | `GET /base/feestationexit/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="244642438"]`(ONLY_JAVA); `rows[bigId="244643441"]`(ONLY_JAVA); `rows[bigId="244643500"]`(ONLY_JAVA); `rows[bigId="244647881"]`(ONLY_JAVA) …共 7 项 | 否(重试后一致) |
| feestationexit-list-order | `GET /base/feestationexit/list?pageNum=1&pageSize=5&orderByColumn=bigId` | DIFF | 200 | 200 | `rows[bigId="11150377"]`(ONLY_GO); `rows[bigId="11153165"]`(ONLY_GO); `rows[bigId="11205617"]`(ONLY_GO); `rows[bigId="11206905"]`(ONLY_GO); `rows[bigId="11207175"]`(ONLY_GO); `rows[bigId="244651227"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| feestationexit-list-pagesize-1 | `GET /base/feestationexit/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="11150377"]`(ONLY_GO); `rows[bigId="11153165"]`(ONLY_GO); `rows[bigId="11205617"]`(ONLY_GO); `rows[bigId="11206905"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| feestationexit-list-pagesize0 | `GET /base/feestationexit/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="11150377"]`(ONLY_GO); `rows[bigId="11153165"]`(ONLY_GO); `rows[bigId="11205617"]`(ONLY_GO); `rows[bigId="11206905"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| fwqclls-list-farpage | `GET /manager/fwqclls/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=1]`(ONLY_JAVA); `rows[bigId=2]`(ONLY_JAVA); `rows[bigId=3]`(ONLY_JAVA) | 否(重试后一致) |
| fwqclls-list-page2 | `GET /manager/fwqclls/list?pageNum=2&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=1]`(ONLY_JAVA); `rows[bigId=2]`(ONLY_JAVA); `rows[bigId=3]`(ONLY_JAVA) | 否(重试后一致) |
| fwqclls-list-pagesize-1 | `GET /manager/fwqclls/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=1]`(ONLY_GO); `rows[bigId=2]`(ONLY_GO); `rows[bigId=3]`(ONLY_GO) | 否(重试后一致) |
| fwqclls-list-pagesize0 | `GET /manager/fwqclls/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=1]`(ONLY_GO); `rows[bigId=2]`(ONLY_GO); `rows[bigId=3]`(ONLY_GO) | 否(重试后一致) |
| fwqjcxx-list-farpage | `GET /base/fwqjcxx/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="240"]`(ONLY_JAVA); `rows[agentPk="242"]`(ONLY_JAVA); `rows[agentPk="244"]`(ONLY_JAVA) | 否(重试后一致) |
| fwqjcxx-list-order | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | DIFF | 200 | 200 | `rows[agentPk="1"]`(ONLY_GO); `rows[agentPk="15"]`(ONLY_GO); `rows[agentPk="244"]`(ONLY_JAVA); `rows[agentPk="245"]`(ONLY_JAVA); `rows[agentPk="246"]`(ONLY_JAVA); `rows[agentPk="247"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| fwqjcxx-list-pagesize-1 | `GET /base/fwqjcxx/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="1"]`(ONLY_GO); `rows[agentPk="15"]`(ONLY_GO); `rows[agentPk="46"]`(ONLY_GO); `rows[agentPk="50"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| fwqjcxx-list-pagesize0 | `GET /base/fwqjcxx/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="1"]`(ONLY_GO); `rows[agentPk="15"]`(ONLY_GO); `rows[agentPk="46"]`(ONLY_GO); `rows[agentPk="50"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| gantry-full-set | `GET /base/gantry/list?pageNum=1&pageSize=1526` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1000"]`(ONLY_JAVA); `rows[id="1005"]`(ONLY_JAVA); `rows[id="1006"]`(ONLY_JAVA); `rows[id="1008"]`(ONLY_JAVA) …共 528 项 | 否(重试后一致) |
| gantry-list-bigpagesize | `GET /base/gantry/list?pageNum=1&pageSize=5000` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1000"]`(ONLY_JAVA); `rows[id="1005"]`(ONLY_JAVA); `rows[id="1006"]`(ONLY_JAVA); `rows[id="1008"]`(ONLY_JAVA) …共 528 项 | 否(重试后一致) |
| gantry-list-farpage | `GET /base/gantry/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1905"]`(ONLY_JAVA) | 否(重试后一致) |
| gantry-list-order | `GET /base/gantry/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=desc` | DIFF | 200 | 200 | `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO); `rows[id="30"]`(ONLY_GO); `rows[id="32"]`(ONLY_GO); `rows[id="36"]`(ONLY_GO); `rows[id="995"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| gantry-list-pagesize-1 | `GET /base/gantry/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="105"]`(ONLY_GO); `rows[id="107"]`(ONLY_GO); `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| gantry-list-pagesize0 | `GET /base/gantry/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="105"]`(ONLY_GO); `rows[id="107"]`(ONLY_GO); `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| gantryIp-full-set | `GET /base/gantryIp/list?pageNum=1&pageSize=1033` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=1001]`(ONLY_JAVA); `rows[id=1002]`(ONLY_JAVA); `rows[id=1003]`(ONLY_JAVA); `rows[id=1004]`(ONLY_JAVA) …共 35 项 | 否(重试后一致) |
| gantryIp-list-bigpagesize | `GET /base/gantryIp/list?pageNum=1&pageSize=5000` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=1001]`(ONLY_JAVA); `rows[id=1002]`(ONLY_JAVA); `rows[id=1003]`(ONLY_JAVA); `rows[id=1004]`(ONLY_JAVA) …共 35 项 | 否(重试后一致) |
| gantryIp-list-farpage | `GET /base/gantryIp/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=1031]`(ONLY_JAVA); `rows[id=1032]`(ONLY_JAVA); `rows[id=1033]`(ONLY_JAVA) | 否(重试后一致) |
| gantryIp-list-order | `GET /base/gantryIp/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=de` | DIFF | 200 | 200 | `rows[id=1]`(ONLY_GO); `rows[id=1029]`(ONLY_JAVA); `rows[id=1030]`(ONLY_JAVA); `rows[id=1031]`(ONLY_JAVA); `rows[id=1032]`(ONLY_JAVA); `rows[id=1033]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| gantryIp-list-pagesize-1 | `GET /base/gantryIp/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=1]`(ONLY_GO); `rows[id=10]`(ONLY_GO); `rows[id=2]`(ONLY_GO); `rows[id=3]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| gantryIp-list-pagesize0 | `GET /base/gantryIp/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=1]`(ONLY_GO); `rows[id=10]`(ONLY_GO); `rows[id=2]`(ONLY_GO); `rows[id=3]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| org-list-farpage | `GET /base/org/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="25398"]`(ONLY_JAVA) | 否(重试后一致) |
| org-list-order | `GET /base/org/list?pageNum=1&pageSize=5&orderByColumn=bigId&isAsc=desc` | DIFF | 200 | 200 | `rows[bigId="24945"]`(ONLY_GO); `rows[bigId="24947"]`(ONLY_GO); `rows[bigId="24967"]`(ONLY_GO); `rows[bigId="24969"]`(ONLY_GO); `rows[bigId="24975"]`(ONLY_GO); `rows[bigId="25419"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| org-list-pagesize-1 | `GET /base/org/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="24945"]`(ONLY_GO); `rows[bigId="24947"]`(ONLY_GO); `rows[bigId="24967"]`(ONLY_GO); `rows[bigId="24969"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| org-list-pagesize0 | `GET /base/org/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId="24945"]`(ONLY_GO); `rows[bigId="24947"]`(ONLY_GO); `rows[bigId="24967"]`(ONLY_GO); `rows[bigId="24969"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| provcapture-filter-tailcapturetime | `GET /base/provcapture/list?pageNum=1&pageSize=5&tailcapturetime=1969-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=312748]`(ONLY_JAVA); `rows[bigId=312775]`(ONLY_JAVA); `rows[bigId=312778]`(ONLY_JAVA); `rows[bigId=312801]`(ONLY_JAVA) …共 8 项 | 否(重试后一致) |
| provcapture-list-farpage | `GET /base/provcapture/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=319831]`(ONLY_JAVA) | 否(重试后一致) |
| provcapture-list-order | `GET /base/provcapture/list?pageNum=1&pageSize=5&orderByColumn=bigId&is` | DIFF | 200 | 200 | `rows[bigId=312748]`(ONLY_GO); `rows[bigId=312775]`(ONLY_GO); `rows[bigId=312778]`(ONLY_GO); `rows[bigId=312801]`(ONLY_GO); `rows[bigId=312805]`(ONLY_GO); `rows[bigId=320326]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| provcapture-list-pagesize-1 | `GET /base/provcapture/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=312706]`(ONLY_GO); `rows[bigId=312710]`(ONLY_GO); `rows[bigId=312748]`(ONLY_GO); `rows[bigId=312775]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| provcapture-list-pagesize0 | `GET /base/provcapture/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=312706]`(ONLY_GO); `rows[bigId=312710]`(ONLY_GO); `rows[bigId=312748]`(ONLY_GO); `rows[bigId=312775]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| large-badtime | `GET /api/v1/large/snapshot?startTime=2025-10-01&endTime=abc&pageNum=1&` | DIFF | 200 | 200 | `code`(VALUE); `data`(KEY_ABSENT); `dataSource`(KEY_ABSENT); `message`(VALUE); `pageNum`(KEY_ABSENT); `pageSize`(KEY_ABSENT) | 否(重试后一致) |
| large-fee | `GET /api/v1/large/fee?startTime=2025-10-01+00%3A00%3A00&endTime=2025-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[bigId="1545746222"]`(ONLY_GO); `data[bigId="1545818359"]`(ONLY_GO); `data[bigId="1545892243"]`(ONLY_GO); `data[bigId="1547071182"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| large-trail | `GET /api/v1/large/trail?startTime=2025-10-01+00%3A00%3A00&endTime=2025` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[0]`(ONLY_GO); `data[1]`(ONLY_GO); `data[2]`(ONLY_GO); `data[3]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| unified-fee | `GET /api/v1/unified/fee/list?startTime=2025-10-01+00%3A00%3A00&endTime` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[bigId="1545746222"]`(ONLY_GO); `data[bigId="1545818359"]`(ONLY_GO); `data[bigId="1545892243"]`(ONLY_GO); `data[bigId="1547071182"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| unified-trail | `GET /api/v1/unified/trail/list?startTime=2025-10-01+00%3A00%3A00&endTi` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `data.<len>`(LEN); `data[0]`(ONLY_GO); `data[1]`(ONLY_GO); `data[2]`(ONLY_GO); `data[3]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| section-list-farpage | `GET /base/section/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="28"]`(ONLY_JAVA); `rows[id="44"]`(ONLY_JAVA); `rows[id="49"]`(ONLY_JAVA); `rows[id="68"]`(ONLY_JAVA) …共 7 项 | 否(重试后一致) |
| section-list-order | `GET /base/section/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=des` | DIFF | 200 | 200 | `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO); `rows[id="30"]`(ONLY_GO); `rows[id="32"]`(ONLY_GO); `rows[id="36"]`(ONLY_GO); `rows[id="87"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| section-list-pagesize-1 | `GET /base/section/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1"]`(ONLY_GO); `rows[id="15"]`(ONLY_GO); `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| section-list-pagesize0 | `GET /base/section/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1"]`(ONLY_GO); `rows[id="15"]`(ONLY_GO); `rows[id="18"]`(ONLY_GO); `rows[id="27"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| sfsjcxx-list-farpage | `GET /base/sfsjcxx/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="004fefdfb7f49292c2166b464f383d58"]`(ONLY_JAVA); `rows[agentPk="9e70a8dd7f78268c74fe936a2a4046ae"]`(ONLY_JAVA); `rows[agentPk="afe2965ed893f0019c544e3619f94e03"]`(ONLY_JAVA); `rows[agentPk="dd0482fff5577fbc9de3469a651dabd5"]`(ONLY_JAVA) | 否(重试后一致) |
| sfsjcxx-list-order | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | DIFF | 200 | 200 | `rows[agentPk="043ec9bbb0470d60bac70845b9dce220"]`(ONLY_GO); `rows[agentPk="104e9b376061bf062bc6679255ff0f0a"]`(ONLY_GO); `rows[agentPk="503ef848c59d4d243df05700fbab4115"]`(ONLY_GO); `rows[agentPk="d2c6df4afa7ff18d48786d728d3919d2"]`(ONLY_GO); `rows[agentPk="d484c29eff416cba362cc882b8c46ed0"]`(ONLY_GO); `rows[agentPk="d7f6454ef24b4a75125bc5e964b778f6"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| sfsjcxx-list-pagesize-1 | `GET /base/sfsjcxx/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="043ec9bbb0470d60bac70845b9dce220"]`(ONLY_GO); `rows[agentPk="104e9b376061bf062bc6679255ff0f0a"]`(ONLY_GO); `rows[agentPk="1ad8e62605562402b7ab8fc3eb97bd13"]`(ONLY_GO); `rows[agentPk="46834078755ec236b5bbe084ee77482a"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| sfsjcxx-list-pagesize0 | `GET /base/sfsjcxx/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="043ec9bbb0470d60bac70845b9dce220"]`(ONLY_GO); `rows[agentPk="104e9b376061bf062bc6679255ff0f0a"]`(ONLY_GO); `rows[agentPk="1ad8e62605562402b7ab8fc3eb97bd13"]`(ONLY_GO); `rows[agentPk="46834078755ec236b5bbe084ee77482a"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| sfzjcxx-list-farpage | `GET /base/sfzjcxx/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="5f93f983524def3dca464469d2cf9f3e"]`(ONLY_JAVA); `rows[agentPk="696ba13e2b24f6552bedfb513089a4ae"]`(ONLY_JAVA); `rows[agentPk="69adc1e107f7f7d035d7baf04342e1ca"]`(ONLY_JAVA); `rows[agentPk="6da9003b743b65f4c0ccd295cc484e57"]`(ONLY_JAVA) …共 7 项 | 否(重试后一致) |
| sfzjcxx-list-order | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&orderByColumn=agentPk&isAs` | DIFF | 200 | 200 | `rows[agentPk="1a71c173106146004259eef9540027d3"]`(ONLY_GO); `rows[agentPk="363bc7b76e508c55dcb259cf6a3f007e"]`(ONLY_GO); `rows[agentPk="6a4585227b16ec3d545152206a5b31f0"]`(ONLY_GO); `rows[agentPk="84d9ee44e457ddef7f2c4f25dc8fa865"]`(ONLY_GO); `rows[agentPk="c7e1249ffc03eb9ded908c236bd1996d"]`(ONLY_GO); `rows[agentPk="fbd7939d674997cdb4692d34de8633c4"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| sfzjcxx-list-pagesize-1 | `GET /base/sfzjcxx/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="1a71c173106146004259eef9540027d3"]`(ONLY_GO); `rows[agentPk="363bc7b76e508c55dcb259cf6a3f007e"]`(ONLY_GO); `rows[agentPk="3f26732132175681f6f8369f3b61a0c7"]`(ONLY_GO); `rows[agentPk="65b9eea6e1cc6bb9f0cd2a47751a186f"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| sfzjcxx-list-pagesize0 | `GET /base/sfzjcxx/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[agentPk="1a71c173106146004259eef9540027d3"]`(ONLY_GO); `rows[agentPk="363bc7b76e508c55dcb259cf6a3f007e"]`(ONLY_GO); `rows[agentPk="3f26732132175681f6f8369f3b61a0c7"]`(ONLY_GO); `rows[agentPk="65b9eea6e1cc6bb9f0cd2a47751a186f"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| snapshotflow-list-pagesize-1 | `GET /base/snapshotflow/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="018551a7-4bb9-48c1-95bd-e7d984dfe867"]`(ONLY_GO); `rows[id="14cefd18-3367-4812-9c4b-eda29d0291c9"]`(ONLY_GO); `rows[id="1cc0cacf-c424-42f8-a862-16d422bc5b59"]`(ONLY_GO); `rows[id="40231010-ad71-48f2-97cb-68dfef10e56a"]`(ONLY_GO) …共 13 项 | 否(重试后一致) |
| snapshotflow-list-pagesize0 | `GET /base/snapshotflow/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="343afb7a-f7ba-42ac-8388-65b94c3b1e47"]`(ONLY_GO); `rows[id="4e6a92f4-e5ea-43d4-9039-f1deede129d5"]`(ONLY_GO); `rows[id="524cdff9-773d-4e28-9137-400014cfccc0"]`(ONLY_GO); `rows[id="709107b1-08f5-4eb5-b408-2be7f09a6281"]`(ONLY_GO) …共 13 项 | 否(重试后一致) |
| stationcapture-list-farpage | `GET /base/stationcapture/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=45952447]`(ONLY_JAVA) | 否(重试后一致) |
| stationcapture-list-order | `GET /base/stationcapture/list?pageNum=1&pageSize=5&orderByColumn=bigId` | DIFF | 200 | 200 | `rows[bigId=20113483]`(ONLY_GO); `rows[bigId=20113519]`(ONLY_GO); `rows[bigId=20114634]`(ONLY_GO); `rows[bigId=20114636]`(ONLY_GO); `rows[bigId=20170979]`(ONLY_GO); `rows[bigId=64873334]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| stationcapture-list-pagesize-1 | `GET /base/stationcapture/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=20113483]`(ONLY_GO); `rows[bigId=20113519]`(ONLY_GO); `rows[bigId=20114634]`(ONLY_GO); `rows[bigId=20114636]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| stationcapture-list-pagesize0 | `GET /base/stationcapture/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[bigId=20113483]`(ONLY_GO); `rows[bigId=20113519]`(ONLY_GO); `rows[bigId=20114634]`(ONLY_GO); `rows[bigId=20114636]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| change-post | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailList[sectionCode=""]`(ONLY_GO); `trailList[sectionCode=null]`(ONLY_JAVA) | 否(重试后一致) |
| change-post-empty | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailUuid`(NULLISH) | 否(重试后一致) |
| change-post-notrail | `POST /base/sysutil/changeTrailInfo` | DIFF | 200 | 200 | `trailUuid`(NULLISH) | 否(重试后一致) |
| getbytrailbo-t1 | `GET /base/sysutil/getByTrailBo?type=1&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t2 | `GET /base/sysutil/getByTrailBo?type=2&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t3 | `GET /base/sysutil/getByTrailBo?type=3&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t4 | `GET /base/sysutil/getByTrailBo?type=4&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t5 | `GET /base/sysutil/getByTrailBo?type=5&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t6 | `GET /base/sysutil/getByTrailBo?type=6&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t7 | `GET /base/sysutil/getByTrailBo?type=7&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-t8 | `GET /base/sysutil/getByTrailBo?type=8&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| getbytrailbo-tempty | `GET /base/sysutil/getByTrailBo?type=&plateNo=%E8%B5%A3AF12345&uuid=0` | DIFF | 200 | 200 | `captureTime`(NULLISH); `devCode`(NULLISH); `devName`(NULLISH); `direction`(NULLISH); `ipType`(NULLISH); `isQuery`(NULLISH) …共 26 项 | 否(重试后一致) |
| syncsuspicious-commented | `POST /base/sysutil/syncSuspiciousCar` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| synctrack-commented | `POST /base/sysutil/syncTrack` | DIFF | 404 | 404 | `code`(KEY_ABSENT); `error`(KEY_ABSENT); `message`(KEY_ABSENT); `msg`(KEY_ABSENT); `path`(KEY_ABSENT); `status`(KEY_ABSENT) | 否(重试后一致) |
| toll-list-farpage | `GET /base/toll/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="619"]`(ONLY_JAVA) | 否(重试后一致) |
| toll-list-order | `GET /base/toll/list?pageNum=1&pageSize=5&orderByColumn=id&isAsc=desc` | DIFF | 200 | 200 | `rows[id="1"]`(ONLY_GO); `rows[id="15"]`(ONLY_GO); `rows[id="46"]`(ONLY_GO); `rows[id="50"]`(ONLY_GO); `rows[id="52"]`(ONLY_GO); `rows[id="92"]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| toll-list-pagesize-1 | `GET /base/toll/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1"]`(ONLY_GO); `rows[id="15"]`(ONLY_GO); `rows[id="46"]`(ONLY_GO); `rows[id="50"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| toll-list-pagesize0 | `GET /base/toll/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id="1"]`(ONLY_GO); `rows[id="15"]`(ONLY_GO); `rows[id="46"]`(ONLY_GO); `rows[id="50"]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| tollStationIp-list-farpage | `GET /base/tollStationIp/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=40285]`(ONLY_JAVA); `rows[id=40302]`(ONLY_JAVA) | 否(重试后一致) |
| tollStationIp-list-order | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&orderByColumn=id&isA` | DIFF | 200 | 200 | `rows[id=40017]`(ONLY_GO); `rows[id=40025]`(ONLY_GO); `rows[id=40031]`(ONLY_GO); `rows[id=40041]`(ONLY_GO); `rows[id=40042]`(ONLY_GO); `rows[id=40304]`(ONLY_JAVA) …共 10 项 | 否(重试后一致) |
| tollStationIp-list-pagesize-1 | `GET /base/tollStationIp/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=40017]`(ONLY_GO); `rows[id=40025]`(ONLY_GO); `rows[id=40031]`(ONLY_GO); `rows[id=40041]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| tollStationIp-list-pagesize0 | `GET /base/tollStationIp/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[id=40017]`(ONLY_GO); `rows[id=40025]`(ONLY_GO); `rows[id=40031]`(ONLY_GO); `rows[id=40041]`(ONLY_GO) …共 12 项 | 否(重试后一致) |
| trailtracks-filter-enterTime | `GET /base/trailtracks/list?pageNum=1&pageSize=5&enterTime=2025-09-10+0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO); `rows[uuid="a204c869-e5cd-4c23-aa7f-073acc7c8056"]`(ONLY_GO); `rows[uuid="e0e22490-fb40-4795-947b-68565d864aa7"]`(ONLY_GO) …共 7 项 | 否(重试后一致) |
| trailtracks-filter-plateKey | `GET /base/trailtracks/list?pageNum=1&pageSize=5&plateKey=%E8%B5%A3CEA8` | DIFF | 200 | 200 | `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO); `rows[uuid="a204c869-e5cd-4c23-aa7f-073acc7c8056"]`(ONLY_GO); `rows[uuid="e0e22490-fb40-4795-947b-68565d864aa7"].pointCount`(VALUE); `rows[uuid="e0e22490-fb40-4795-947b-68565d864aa7"].trailPoints`(VALUE); `total`(VALUE) | 否(重试后一致) |
| trailtracks-filter-pointCount | `GET /base/trailtracks/list?pageNum=1&pageSize=5&pointCount=45` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="1e8f9d50-3af8-4fbf-bd05-41870f67d95d"]`(ONLY_JAVA); `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO); `rows[uuid="a204c869-e5cd-4c23-aa7f-073acc7c8056"]`(ONLY_GO) …共 9 项 | 否(重试后一致) |
| trailtracks-filter-type | `GET /base/trailtracks/list?pageNum=1&pageSize=5&type=0` | DIFF | 200 | 200 | `total`(VALUE) | 否(重试后一致) |
| trailtracks-full-set | `GET /base/trailtracks/list?pageNum=1&pageSize=1379` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="0132c534-b5ef-4982-bbd1-ef2067bac85b"]`(ONLY_JAVA); `rows[uuid="03cdd28c-f01d-4670-b7f8-b86c5a9d6ceb"]`(ONLY_JAVA); `rows[uuid="05820c71-2e3a-4f0e-acb8-feab7f80fb54"]`(ONLY_JAVA); `rows[uuid="06cb9071-bb59-4189-9aa6-10772c05782b"]`(ONLY_JAVA) …共 217 项 | 否(重试后一致) |
| trailtracks-list-bigpagesize | `GET /base/trailtracks/list?pageNum=1&pageSize=5000` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="0132c534-b5ef-4982-bbd1-ef2067bac85b"]`(ONLY_JAVA); `rows[uuid="03cdd28c-f01d-4670-b7f8-b86c5a9d6ceb"]`(ONLY_JAVA); `rows[uuid="05820c71-2e3a-4f0e-acb8-feab7f80fb54"]`(ONLY_JAVA); `rows[uuid="06cb9071-bb59-4189-9aa6-10772c05782b"]`(ONLY_JAVA) …共 217 项 | 否(重试后一致) |
| trailtracks-list-farpage | `GET /base/trailtracks/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="32f28930-d375-4ce7-a916-de552c05f4dd"]`(ONLY_JAVA) | 否(重试后一致) |
| trailtracks-list-order | `GET /base/trailtracks/list?pageNum=1&pageSize=5&orderByColumn=uuid&isA` | DIFF | 200 | 200 | `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO); `rows[uuid="a204c869-e5cd-4c23-aa7f-073acc7c8056"]`(ONLY_GO); `rows[uuid="e0e22490-fb40-4795-947b-68565d864aa7"]`(ONLY_GO); `rows[uuid="fe15c2f8-0094-40cc-846c-39b13b548fcf"]`(ONLY_JAVA); `rows[uuid="fe2b6c0e-0742-4431-949a-d8f9bbe50557"]`(ONLY_JAVA) …共 9 项 | 否(重试后一致) |
| trailtracks-list-pagesize-1 | `GET /base/trailtracks/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="010b75a4-b35e-4d54-86f7-919d63f599dd"]`(ONLY_GO); `rows[uuid="1e8f9d50-3af8-4fbf-bd05-41870f67d95d"]`(ONLY_GO); `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO) …共 10 项 | 否(重试后一致) |
| trailtracks-list-pagesize0 | `GET /base/trailtracks/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid="010b75a4-b35e-4d54-86f7-919d63f599dd"]`(ONLY_GO); `rows[uuid="1e8f9d50-3af8-4fbf-bd05-41870f67d95d"]`(ONLY_GO); `rows[uuid="54e6eac4-9fd6-4fe5-bbbe-584129cfba08"]`(ONLY_GO); `rows[uuid="9bd0680c-6ecc-45b1-a7ca-c2e348c2adaa"]`(ONLY_GO) …共 10 项 | 否(重试后一致) |
| vehicleweight-list-farpage | `GET /base/vehicleweight/list?pageNum=99999&pageSize=5` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid=null]`(ONLY_JAVA) | 否(重试后一致) |
| vehicleweight-list-pagesize-1 | `GET /base/vehicleweight/list?pageNum=1&pageSize=-1` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid=null]`(ONLY_GO) | 否(重试后一致) |
| vehicleweight-list-pagesize0 | `GET /base/vehicleweight/list?pageNum=1&pageSize=0` | DIFF | 200 | 200 | `root.<rows_len>`(LEN); `rows.<len>`(LEN); `rows[uuid=null]`(ONLY_GO) | 否(重试后一致) |
| sql-ish-param | `GET /base/gantry/list?gantryName=O%27Brien&pageSize=5` | OK | 200 | 200 | - | 是 |
| type-mismatch | `GET /base/gantry/list?pageSize=abc` | OK | 200 | 200 | - | 是 |
| unicode-param | `GET /base/gantry/list?gantryName=%E7%91%9E%E9%87%91%E5%8C%97+%E4%BA%92` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_full | `POST /api/v1/large/sync/full` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_incremental | `POST /api/v1/large/sync/incremental` | OK | 200 | 200 | - | 是 |
| exists_api_v1_large_sync_repair | `POST /api/v1/large/sync/repair` | OK | 400 | 400 | - | 是 |
| exists_base_sysutilTest_separateSnapshotFlowTimeList | `POST /base/sysutilTest/separateSnapshotFlowTimeList` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncBaseInfo | `POST /base/sysutilTest/syncBaseInfo` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncCurrentTrack | `POST /base/sysutilTest/syncCurrentTrack` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncHistroyTrack | `POST /base/sysutilTest/syncHistroyTrack` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncOdsSzdnGantry | `POST /base/sysutilTest/syncOdsSzdnGantry` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar | `POST /base/sysutilTest/syncSuspiciousCar` | OK | 404 | 404 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar1 | `POST /base/sysutilTest/syncSuspiciousCar1` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar10 | `POST /base/sysutilTest/syncSuspiciousCar10` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar2 | `POST /base/sysutilTest/syncSuspiciousCar2` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar3 | `POST /base/sysutilTest/syncSuspiciousCar3` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar4 | `POST /base/sysutilTest/syncSuspiciousCar4` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar5 | `POST /base/sysutilTest/syncSuspiciousCar5` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar6 | `POST /base/sysutilTest/syncSuspiciousCar6` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar7 | `POST /base/sysutilTest/syncSuspiciousCar7` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar8 | `POST /base/sysutilTest/syncSuspiciousCar8` | OK | 405 | 405 | - | 是 |
| exists_base_sysutilTest_syncSuspiciousCar9 | `POST /base/sysutilTest/syncSuspiciousCar9` | OK | 405 | 405 | - | 是 |
| exists_base_sysutil_saveRedis | `POST /base/sysutil/saveRedis` | OK | 405 | 405 | - | 是 |
| feeGantry-info | `GET /base/feeGantry/59?bigId=59` | OK | 200 | 200 | - | 是 |
| feeGantry-info-miss | `GET /base/feeGantry/__no_such_id__` | OK | 200 | 200 | both unparsable | 是 |
| feeStationEnter-filter-cardid | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&cardid=15012312232` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-electricalpercentage | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&electricalpercenta` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-enaxlecount | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&enaxlecount=2` | OK | 200 | 200 | - | 是 |
| feeStationEnter-filter-entime | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5&entime=2024-11-24` | OK | 200 | 200 | - | 是 |
| feeStationEnter-full-set | `GET /base/feeStationEnter/list?pageNum=1&pageSize=317` | OK | 200 | 200 | - | 是 |
| feeStationEnter-info | `GET /base/feeStationEnter/2308?bigId=2308` | OK | 200 | 200 | - | 是 |
| feeStationEnter-info-badid | `GET /base/feeStationEnter/not-a-number` | OK | 400 | 400 | - | 是 |
| feeStationEnter-info-miss | `GET /base/feeStationEnter/__no_such_id__` | OK | 400 | 400 | - | 是 |
| feeStationEnter-list-bigpagesize | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-default | `GET /base/feeStationEnter/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-noargs | `GET /base/feeStationEnter/list` | OK | 200 | 200 | - | 是 |
| feeStationEnter-list-page2 | `GET /base/feeStationEnter/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-actualfeeclass | `GET /base/feestationexit/list?pageNum=1&pageSize=5&actualfeeclass=0` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-axlecount | `GET /base/feestationexit/list?pageNum=1&pageSize=5&axlecount=2` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-discountfee | `GET /base/feestationexit/list?pageNum=1&pageSize=5&discountfee=0` | OK | 200 | 200 | - | 是 |
| feestationexit-filter-electricalpercentage | `GET /base/feestationexit/list?pageNum=1&pageSize=5&electricalpercentag` | OK | 200 | 200 | - | 是 |
| feestationexit-full-set | `GET /base/feestationexit/list?pageNum=1&pageSize=270` | OK | 200 | 200 | - | 是 |
| feestationexit-info | `GET /base/feestationexit/11150377?bigId=11150377` | OK | 200 | 200 | - | 是 |
| feestationexit-info-miss | `GET /base/feestationexit/__no_such_id__` | OK | 200 | 200 | - | 是 |
| feestationexit-list-bigpagesize | `GET /base/feestationexit/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| feestationexit-list-default | `GET /base/feestationexit/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| feestationexit-list-noargs | `GET /base/feestationexit/list` | OK | 200 | 200 | - | 是 |
| feestationexit-list-page2 | `GET /base/feestationexit/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqclls-filter-datauuid | `GET /manager/fwqclls/list?pageNum=1&pageSize=5&datauuid=uuid-fwq-20251` | OK | 200 | 200 | - | 是 |
| fwqclls-full-set | `GET /manager/fwqclls/list?pageNum=1&pageSize=3` | OK | 200 | 200 | - | 是 |
| fwqclls-info | `GET /manager/fwqclls/1?bigId=1` | OK | 200 | 200 | - | 是 |
| fwqclls-info-badid | `GET /manager/fwqclls/not-a-number` | OK | 400 | 400 | - | 是 |
| fwqclls-info-miss | `GET /manager/fwqclls/__no_such_id__` | OK | 400 | 400 | - | 是 |
| fwqclls-list-bigpagesize | `GET /manager/fwqclls/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| fwqclls-list-default | `GET /manager/fwqclls/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqclls-list-noargs | `GET /manager/fwqclls/list` | OK | 200 | 200 | - | 是 |
| fwqclls-list-order | `GET /manager/fwqclls/list?pageNum=1&pageSize=5&orderByColumn=bigId&isA` | OK | 200 | 200 | - | 是 |
| fwqjcxx-filter-fwqbm | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&fwqbm=G0321361123W0010` | OK | 200 | 200 | - | 是 |
| fwqjcxx-filter-fwqmc | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5&fwqmc=%E4%B8%89%E6%B8%85%E` | OK | 200 | 200 | - | 是 |
| fwqjcxx-full-set | `GET /base/fwqjcxx/list?pageNum=1&pageSize=218` | OK | 200 | 200 | - | 是 |
| fwqjcxx-info | `GET /base/fwqjcxx/1?agentPk=1` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-bigpagesize | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-default | `GET /base/fwqjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-noargs | `GET /base/fwqjcxx/list` | OK | 200 | 200 | - | 是 |
| fwqjcxx-list-page2 | `GET /base/fwqjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| fwqjcxx-listAll | `GET /base/fwqjcxx/listAll` | OK | 200 | 200 | - | 是 |
| gantry-filter-gantryCode | `GET /base/gantry/list?pageNum=1&pageSize=5&gantryCode=G003536012000720` | OK | 200 | 200 | - | 是 |
| gantry-filter-gantryName | `GET /base/gantry/list?pageNum=1&pageSize=5&gantryName=%E7%91%9E%E9%87%` | OK | 200 | 200 | - | 是 |
| gantry-filter-roadCode | `GET /base/gantry/list?pageNum=1&pageSize=5&roadCode=G35` | OK | 200 | 200 | - | 是 |
| gantry-filter-sectionCode | `GET /base/gantry/list?pageNum=1&pageSize=5&sectionCode=200R50035072900` | OK | 200 | 200 | - | 是 |
| gantry-info | `GET /base/gantry/18?id=18` | OK | 200 | 200 | - | 是 |
| gantry-info-miss | `GET /base/gantry/__no_such_id__` | OK | 200 | 200 | - | 是 |
| gantry-list-default | `GET /base/gantry/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantry-list-noargs | `GET /base/gantry/list` | OK | 200 | 200 | - | 是 |
| gantry-list-page2 | `GET /base/gantry/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantry-listAll | `GET /base/gantry/listAll` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-gantryCode | `GET /base/gantryIp/list?pageNum=1&pageSize=5&gantryCode=S0036360110005` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-gantryName | `GET /base/gantryIp/list?pageNum=1&pageSize=5&gantryName=%E5%8D%97%E5%A` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-ip | `GET /base/gantryIp/list?pageNum=1&pageSize=5&ip=36.121.3.43` | OK | 200 | 200 | - | 是 |
| gantryIp-filter-orgCode | `GET /base/gantryIp/list?pageNum=1&pageSize=5&orgCode=020000253` | OK | 200 | 200 | - | 是 |
| gantryIp-info | `GET /base/gantryIp/1?id=1` | OK | 200 | 200 | - | 是 |
| gantryIp-info-badid | `GET /base/gantryIp/not-a-number` | OK | 400 | 400 | - | 是 |
| gantryIp-info-miss | `GET /base/gantryIp/__no_such_id__` | OK | 400 | 400 | - | 是 |
| gantryIp-list-default | `GET /base/gantryIp/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| gantryIp-list-noargs | `GET /base/gantryIp/list` | OK | 200 | 200 | - | 是 |
| gantryIp-list-page2 | `GET /base/gantryIp/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-filter-orgCode | `GET /base/org/list?pageNum=1&pageSize=5&orgCode=000000936` | OK | 200 | 200 | - | 是 |
| org-filter-orgName | `GET /base/org/list?pageNum=1&pageSize=5&orgName=%E4%B8%AD%E5%BF%83%E6%` | OK | 200 | 200 | - | 是 |
| org-filter-orgParentId | `GET /base/org/list?pageNum=1&pageSize=5&orgParentId=030000009` | OK | 200 | 200 | - | 是 |
| org-filter-orgShortName | `GET /base/org/list?pageNum=1&pageSize=5&orgShortName=%E4%B8%AD%E5%BF%8` | OK | 200 | 200 | - | 是 |
| org-full-set | `GET /base/org/list?pageNum=1&pageSize=481` | OK | 200 | 200 | - | 是 |
| org-info | `GET /base/org/24945?bigId=24945` | OK | 200 | 200 | - | 是 |
| org-info-miss | `GET /base/org/__no_such_id__` | OK | 200 | 200 | - | 是 |
| org-list-bigpagesize | `GET /base/org/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| org-list-default | `GET /base/org/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-list-noargs | `GET /base/org/list` | OK | 200 | 200 | - | 是 |
| org-list-page2 | `GET /base/org/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| org-listAll | `GET /base/org/listAll` | OK | 200 | 200 | - | 是 |
| provcapture-filter-deviceip | `GET /base/provcapture/list?pageNum=1&pageSize=5&deviceip=36.101.189.5` | OK | 200 | 200 | - | 是 |
| provcapture-filter-platecolorcode | `GET /base/provcapture/list?pageNum=1&pageSize=5&platecolorcode=1` | OK | 200 | 200 | - | 是 |
| provcapture-filter-tailcapturetimeunix | `GET /base/provcapture/list?pageNum=1&pageSize=5&tailcapturetimeunix=-2` | OK | 200 | 200 | - | 是 |
| provcapture-full-set | `GET /base/provcapture/list?pageNum=1&pageSize=356` | OK | 200 | 200 | - | 是 |
| provcapture-info | `GET /base/provcapture/312748?bigId=312748` | OK | 200 | 200 | - | 是 |
| provcapture-info-badid | `GET /base/provcapture/not-a-number` | OK | 400 | 400 | - | 是 |
| provcapture-info-miss | `GET /base/provcapture/__no_such_id__` | OK | 400 | 400 | - | 是 |
| provcapture-list-bigpagesize | `GET /base/provcapture/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| provcapture-list-default | `GET /base/provcapture/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| provcapture-list-noargs | `GET /base/provcapture/list` | OK | 200 | 200 | - | 是 |
| provcapture-list-page2 | `GET /base/provcapture/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| export-status-unknown | `GET /api/v1/large/export/status/nope` | OK | 200 | 200 | - | 是 |
| large-cartrack | `GET /api/v1/large/carTrackQueryByCarNo?carNo=%E8%B5%A3AF12345&startTim` | OK | 200 | 200 | - | 是 |
| large-fuzzy | `GET /api/v1/large/snapshot?startTime=2025-10-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| large-missing-arg | `GET /api/v1/large/snapshot?endTime=2025-10-02+00%3A00%3A00` | OK | 400 | 400 | - | 是 |
| large-snapshot | `GET /api/v1/large/snapshot?startTime=2025-10-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| large-stats | `GET /api/v1/large/stats/group?type=snapshot&startTime=2025-10-01+00%3A` | OK | 200 | 200 | - | 是 |
| large-stats-badgroup | `GET /api/v1/large/stats/group?type=snapshot&startTime=2025-10-01+00%3A` | OK | 200 | 200 | - | 是 |
| large-window-huge | `GET /api/v1/large/snapshot?startTime=2025-09-01+00%3A00%3A00&endTime=2` | OK | 200 | 200 | - | 是 |
| prog-filter | `GET /progressive/snapshotflow/list?startTime=2025-10-01+00%3A00%3A00&e` | OK | 200 | 200 | - | 是 |
| prog-noargs | `GET /progressive/snapshotflow/list` | OK | 200 | 200 | - | 是 |
| prog-scalelevel | `GET /progressive/scale-level` | OK | 200 | 200 | - | 是 |
| prog-snapshotflow | `GET /progressive/snapshotflow/list?startTime=2025-10-01+00%3A00%3A00&e` | OK | 200 | 200 | - | 是 |
| unified-baddb | `GET /api/v1/unified/__nope__/list?startTime=2025-10-01+00%3A00%3A00&en` | OK | 200 | 200 | - | 是 |
| unified-export-status-unknown | `GET /api/v1/unified/export/status/nope` | OK | 200 | 200 | - | 是 |
| unified-snapshot | `GET /api/v1/unified/snapshot/list?startTime=2025-10-01+00%3A00%3A00&en` | OK | 200 | 200 | - | 是 |
| section-filter-roadCode | `GET /base/section/list?pageNum=1&pageSize=5&roadCode=G6021` | OK | 200 | 200 | - | 是 |
| section-filter-roadName | `GET /base/section/list?pageNum=1&pageSize=5&roadName=%E6%9D%AD%E9%95%B` | OK | 200 | 200 | - | 是 |
| section-filter-sectionCode | `GET /base/section/list?pageNum=1&pageSize=5&sectionCode=200R5602106710` | OK | 200 | 200 | - | 是 |
| section-filter-sectionName | `GET /base/section/list?pageNum=1&pageSize=5&sectionName=%E4%B9%90%E6%B` | OK | 200 | 200 | - | 是 |
| section-full-set | `GET /base/section/list?pageNum=1&pageSize=85` | OK | 200 | 200 | - | 是 |
| section-info | `GET /base/section/18?id=18` | OK | 200 | 200 | - | 是 |
| section-info-miss | `GET /base/section/__no_such_id__` | OK | 200 | 200 | - | 是 |
| section-list-bigpagesize | `GET /base/section/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| section-list-default | `GET /base/section/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| section-list-noargs | `GET /base/section/list` | OK | 200 | 200 | - | 是 |
| section-list-page2 | `GET /base/section/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| section-listAll | `GET /base/section/listAll` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-jd | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&jd=117.43187400` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-sfsmc | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&sfsmc=%E4%B8%8A%E4%B8%87%E` | OK | 200 | 200 | - | 是 |
| sfsjcxx-filter-yxtzj | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5&yxtzj=1531950771411013633` | OK | 200 | 200 | - | 是 |
| sfsjcxx-full-set | `GET /base/sfsjcxx/list?pageNum=1&pageSize=24` | OK | 200 | 200 | - | 是 |
| sfsjcxx-info | `GET /base/sfsjcxx/d2c6df4afa7ff18d48786d728d3919d2?agentPk=d2c6df4afa7` | OK | 200 | 200 | - | 是 |
| sfsjcxx-info-miss | `GET /base/sfsjcxx/__no_such_id__` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-bigpagesize | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-default | `GET /base/sfsjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-noargs | `GET /base/sfsjcxx/list` | OK | 200 | 200 | - | 是 |
| sfsjcxx-list-page2 | `GET /base/sfsjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfsjcxx-listAll | `GET /base/sfsjcxx/listAll` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-agentPk | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&agentPk=363bc7b76e508c55dc` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-sfzdm | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&sfzdm=G56360429F0010` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-sfzmc | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&sfzmc=%E5%9D%87%E6%A1%A5%E` | OK | 200 | 200 | - | 是 |
| sfzjcxx-filter-yxtzj | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5&yxtzj=1495673117678645249` | OK | 200 | 200 | - | 是 |
| sfzjcxx-full-set | `GET /base/sfzjcxx/list?pageNum=1&pageSize=320` | OK | 200 | 200 | - | 是 |
| sfzjcxx-info | `GET /base/sfzjcxx/363bc7b76e508c55dcb259cf6a3f007e?agentPk=363bc7b76e5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-info-miss | `GET /base/sfzjcxx/__no_such_id__` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-bigpagesize | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-default | `GET /base/sfzjcxx/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-noargs | `GET /base/sfzjcxx/list` | OK | 200 | 200 | - | 是 |
| sfzjcxx-list-page2 | `GET /base/sfzjcxx/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| sfzjcxx-listAll | `GET /base/sfzjcxx/listAll` | OK | 200 | 200 | - | 是 |
| snapshotflow-info | `GET /base/snapshotflow/f249ade5f48041cc983c4b0232fa8c2f?bigId=f249ade5` | OK | 200 | 200 | both unparsable | 是 |
| snapshotflow-info-miss | `GET /base/snapshotflow/__no_such_id__` | OK | 200 | 200 | both unparsable | 是 |
| stationcapture-filter-cameratype | `GET /base/stationcapture/list?pageNum=1&pageSize=5&cameratype=StationC` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-datasource | `GET /base/stationcapture/list?pageNum=1&pageSize=5&datasource=ZdTrails` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-deviceid | `GET /base/stationcapture/list?pageNum=1&pageSize=5&deviceid=00000000` | OK | 200 | 200 | - | 是 |
| stationcapture-filter-deviceip | `GET /base/stationcapture/list?pageNum=1&pageSize=5&deviceip=36.105.104` | OK | 200 | 200 | - | 是 |
| stationcapture-full-set | `GET /base/stationcapture/list?pageNum=1&pageSize=851` | OK | 200 | 200 | - | 是 |
| stationcapture-info | `GET /base/stationcapture/20113483?bigId=20113483` | OK | 200 | 200 | - | 是 |
| stationcapture-info-badid | `GET /base/stationcapture/not-a-number` | OK | 400 | 400 | - | 是 |
| stationcapture-info-miss | `GET /base/stationcapture/__no_such_id__` | OK | 400 | 400 | - | 是 |
| stationcapture-list-bigpagesize | `GET /base/stationcapture/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| stationcapture-list-default | `GET /base/stationcapture/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| stationcapture-list-noargs | `GET /base/stationcapture/list` | OK | 200 | 200 | - | 是 |
| stationcapture-list-page2 | `GET /base/stationcapture/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| cartrack-blank | `GET /base/sysutil/carTrackQueryByCarNo?plateNo=&pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-filter-idCard | `GET /base/toll/list?pageNum=1&pageSize=5&idCard=44L4464527980850000` | OK | 200 | 200 | - | 是 |
| toll-filter-roadCode | `GET /base/toll/list?pageNum=1&pageSize=5&roadCode=S43` | OK | 200 | 200 | - | 是 |
| toll-filter-tollCode | `GET /base/toll/list?pageNum=1&pageSize=5&tollCode=S43361002F0020` | OK | 200 | 200 | - | 是 |
| toll-filter-tollName | `GET /base/toll/list?pageNum=1&pageSize=5&tollName=%E6%8A%9A%E5%B7%9E%E` | OK | 200 | 200 | - | 是 |
| toll-full-set | `GET /base/toll/list?pageNum=1&pageSize=321` | OK | 200 | 200 | - | 是 |
| toll-info | `GET /base/toll/1?id=1` | OK | 200 | 200 | - | 是 |
| toll-info-miss | `GET /base/toll/__no_such_id__` | OK | 200 | 200 | - | 是 |
| toll-list-bigpagesize | `GET /base/toll/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| toll-list-default | `GET /base/toll/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-list-noargs | `GET /base/toll/list` | OK | 200 | 200 | - | 是 |
| toll-list-page2 | `GET /base/toll/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| toll-listAll | `GET /base/toll/listAll` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-ip | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&ip=36.106.145.9` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-orgCode | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&orgCode=030000008` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-tollCode | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&tollCode=S0089360020` | OK | 200 | 200 | - | 是 |
| tollStationIp-filter-tollName | `GET /base/tollStationIp/list?pageNum=1&pageSize=5&tollName=%E8%8E%B2%E` | OK | 200 | 200 | - | 是 |
| tollStationIp-full-set | `GET /base/tollStationIp/list?pageNum=1&pageSize=302` | OK | 200 | 200 | - | 是 |
| tollStationIp-info | `GET /base/tollStationIp/40017?id=40017` | OK | 200 | 200 | - | 是 |
| tollStationIp-info-badid | `GET /base/tollStationIp/not-a-number` | OK | 400 | 400 | - | 是 |
| tollStationIp-info-miss | `GET /base/tollStationIp/__no_such_id__` | OK | 400 | 400 | - | 是 |
| tollStationIp-list-bigpagesize | `GET /base/tollStationIp/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-default | `GET /base/tollStationIp/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-noargs | `GET /base/tollStationIp/list` | OK | 200 | 200 | - | 是 |
| tollStationIp-list-page2 | `GET /base/tollStationIp/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| trailtracks-info-miss | `GET /base/trailtracks/__no_such_id__` | OK | 200 | 200 | - | 是 |
| trailtracks-list-default | `GET /base/trailtracks/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| trailtracks-list-noargs | `GET /base/trailtracks/list` | OK | 200 | 200 | - | 是 |
| trailtracks-list-page2 | `GET /base/trailtracks/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-full-set | `GET /base/vehicleweight/list?pageNum=1&pageSize=300` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-bigpagesize | `GET /base/vehicleweight/list?pageNum=1&pageSize=5000` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-default | `GET /base/vehicleweight/list?pageNum=1&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-noargs | `GET /base/vehicleweight/list` | OK | 200 | 200 | - | 是 |
| vehicleweight-list-page2 | `GET /base/vehicleweight/list?pageNum=2&pageSize=5` | OK | 200 | 200 | - | 是 |
| vehicleweight-map | `GET /base/vehicleweight/map` | OK | 200 | 200 | - | 是 |
